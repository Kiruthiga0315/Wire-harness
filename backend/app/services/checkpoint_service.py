from __future__ import annotations

import math
import numpy as np
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Checkpoint, ProductModel
from app.schemas.checkpoint import CheckpointCreate, CheckpointUpdate


class ModelNotFoundError(LookupError):
    pass


class CheckpointNotFoundError(LookupError):
    pass


class DuplicateCheckpointError(ValueError):
    pass


class CheckpointService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_model(self, model_id: str) -> list[Checkpoint]:
        self._require_model(model_id)
        statement = (
            select(Checkpoint)
            .where(Checkpoint.model_id == model_id)
            .order_by(Checkpoint.id)
        )
        return list(self.session.scalars(statement))

    def create(self, model_id: str, payload: CheckpointCreate) -> Checkpoint:
        self._require_model(model_id)
        data = payload.model_dump(exclude={"checkpoint_id"})
        checkpoint = Checkpoint(
            **data,
            model_id=model_id,
            checkpoint_id=payload.checkpoint_id or self._next_checkpoint_id(model_id),
        )
        self.session.add(checkpoint)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise DuplicateCheckpointError("Checkpoint ID already exists for this model") from exc
        self.session.refresh(checkpoint)
        return checkpoint

    def update(self, model_id: str, checkpoint_id: str, payload: CheckpointUpdate) -> Checkpoint:
        checkpoint = self._require_checkpoint(model_id, checkpoint_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(checkpoint, field, value)
        self.session.commit()
        self.session.refresh(checkpoint)
        return checkpoint

    def delete(self, model_id: str, checkpoint_id: str) -> None:
        checkpoint = self._require_checkpoint(model_id, checkpoint_id)
        self.session.delete(checkpoint)
        self.session.commit()

    def sync_from_golden_reference(
        self,
        model_id: str,
        replace: bool = True,
        scale_to_active_image: bool = True,
    ) -> list[Checkpoint]:
        self._require_model(model_id)
        from app.services.active_image_service import active_image_service
        from app.services.golden_reference_service import golden_reference_service

        config = golden_reference_service.get_configuration()
        golden_checkpoints = config.get("checkpoints", [])
        if not golden_checkpoints:
            return self.list_for_model(model_id)

        golden_w = float(config.get("image_width", 1800) or 1800)
        golden_h = float(config.get("image_height", 560) or 560)

        target_w = golden_w
        target_h = golden_h
        if scale_to_active_image:
            active = active_image_service.get_active_image()
            if active is not None and active.width > 0 and active.height > 0:
                active_aspect = active.width / active.height
                golden_aspect = golden_w / golden_h
                # Only scale if aspect ratios match; never crush landscape coordinates into portrait
                if abs(active_aspect - golden_aspect) < 0.5:
                    target_w = float(active.width)
                    target_h = float(active.height)
                else:
                    target_w = golden_w
                    target_h = golden_h
            else:
                target_w = golden_w
                target_h = golden_h

        scale_x = target_w / golden_w
        scale_y = target_h / golden_h
        scale_roi = math.sqrt(scale_x * scale_y) if (scale_x > 0 and scale_y > 0) else 1.0

        is_same_scale = abs(scale_x - 1.0) < 0.02 and abs(scale_y - 1.0) < 0.02

        # Feature snapping to physically detected skeleton endpoints and junctions
        # Only snap when translating between different image resolutions (e.g. demo 681x1584 to 1800x560).
        # When dimensions match, preserve the user's exact manual coordinates without modification.
        snapping_keypoints: list[tuple[int, int]] = []
        if scale_to_active_image and not is_same_scale:
            try:
                active = active_image_service.get_active_image()
                if active is not None and active.bgr_image is not None:
                    from app.services.feature_extraction_service import FeatureExtractionService
                    fe = FeatureExtractionService().extract_features(active.bgr_image)
                    snapping_keypoints = [
                        (ep.x, ep.y) for ep in fe.skeleton_features.endpoint_candidates
                    ] + [
                        (j.x, j.y) for j in fe.skeleton_features.junction_candidates
                    ]
            except Exception:
                snapping_keypoints = []

        existing_map = {
            cp.checkpoint_id: cp
            for cp in self.session.scalars(
                select(Checkpoint).where(Checkpoint.model_id == model_id)
            )
        }

        synced_ids: set[str] = set()

        for gcp in golden_checkpoints:
            cid = gcp.get("checkpoint_id")
            if not cid:
                continue
            synced_ids.add(cid)

            # Map category
            gtype = (gcp.get("type") or "terminal").lower()
            if gtype == "terminal":
                category = "Terminal"
            elif gtype == "junction":
                category = "Junction"
            elif gtype == "node_distance":
                category = "Dimension"
            elif gtype == "branch":
                category = "Branch"
            else:
                category = "Connector"

            # Map inspection type
            mtype = (gcp.get("measurement_type") or "branch_length").lower()
            if mtype == "branch_length":
                inspection_type = "Length"
            elif mtype == "node_to_node_distance":
                inspection_type = "Distance"
            elif mtype == "presence":
                inspection_type = "Presence"
            else:
                inspection_type = "Length"

            # Checkpoint name
            notes = gcp.get("notes") or ""
            tid = gcp.get("terminal_id")
            nid = gcp.get("node_id")
            bid = gcp.get("branch_id")
            if notes:
                name = notes
            elif tid:
                name = f"Terminal {tid} ({nid or cid})"
            elif nid:
                name = f"Node {nid}"
            elif bid:
                name = f"Branch {bid}"
            else:
                name = f"Checkpoint {cid}"
            name = name.strip()[:180]

            # Expected value
            exp_val = gcp.get("expected_value")
            if exp_val is not None:
                expected_str = f"{exp_val / 10.0:.1f} cm ({int(exp_val)} mm)"
            else:
                expected_str = "Present"

            # Tolerance in cm
            tol_val = gcp.get("tolerance")
            tolerance = round(tol_val / 10.0, 1) if tol_val is not None else 1.5

            # Scaled coordinates clamped within valid image boundaries
            ref_x = max(0, min(int(target_w), int(round(gcp.get("reference_x", 0) * scale_x))))
            ref_y = max(0, min(int(target_h), int(round(gcp.get("reference_y", 0) * scale_y))))

            # Snap to closest detected feature within 65px radius if available
            if snapping_keypoints:
                closest = min(snapping_keypoints, key=lambda p: math.hypot(p[0] - ref_x, p[1] - ref_y))
                if math.hypot(closest[0] - ref_x, closest[1] - ref_y) <= 65.0:
                    ref_x = max(0, min(int(target_w), int(closest[0])))
                    ref_y = max(0, min(int(target_h), int(closest[1])))

            # Isotropic proportional ROI size to prevent stretched rectangles
            roi_w = max(35, min(80, int(round(gcp.get("roi_width", 45) * scale_roi))))
            roi_h = max(35, min(80, int(round(gcp.get("roi_height", 45) * scale_roi))))

            existing = existing_map.get(cid)
            if existing is not None:
                existing.checkpoint_name = name
                existing.category = category
                existing.inspection_type = inspection_type
                existing.expected_value = expected_str
                existing.tolerance = tolerance
                existing.reference_x = ref_x
                existing.reference_y = ref_y
                existing.roi_width = roi_w
                existing.roi_height = roi_h
                existing.enabled = True
            else:
                new_cp = Checkpoint(
                    checkpoint_id=cid,
                    model_id=model_id,
                    checkpoint_name=name,
                    category=category,
                    inspection_type=inspection_type,
                    expected_value=expected_str,
                    tolerance=tolerance,
                    reference_x=ref_x,
                    reference_y=ref_y,
                    roi_width=roi_w,
                    roi_height=roi_h,
                    enabled=True,
                )
                self.session.add(new_cp)

        # Retain or provide CP-008 for colour inspection compatibility
        if "CP-008" not in synced_ids:
            synced_ids.add("CP-008")
            cp008_x = 438 if (target_w == 1800 and target_h == 560) else int(round(365 * (target_w / 681.0)))
            cp008_y = 276 if (target_w == 1800 and target_h == 560) else int(round(440 * (target_h / 1584.0)))
            existing_cp008 = existing_map.get("CP-008")
            if existing_cp008 is not None:
                existing_cp008.checkpoint_name = "Tape T1 Colour Inspection"
                existing_cp008.category = "Tape"
                existing_cp008.inspection_type = "Colour"
                existing_cp008.expected_value = "Blue"
                existing_cp008.reference_x = cp008_x
                existing_cp008.reference_y = cp008_y
                existing_cp008.roi_width = 80
                existing_cp008.roi_height = 80
                existing_cp008.enabled = True
            else:
                cp008 = Checkpoint(
                    checkpoint_id="CP-008",
                    model_id=model_id,
                    checkpoint_name="Tape T1 Colour Inspection",
                    category="Tape",
                    inspection_type="Colour",
                    expected_value="Blue",
                    tolerance=None,
                    reference_x=cp008_x,
                    reference_y=cp008_y,
                    roi_width=80,
                    roi_height=80,
                    enabled=True,
                )
                self.session.add(cp008)

        if replace:
            for old_id, old_cp in existing_map.items():
                if old_id not in synced_ids:
                    self.session.delete(old_cp)

        self.session.commit()
        return self.list_for_model(model_id)

    def _require_model(self, model_id: str) -> ProductModel:
        model = self.session.scalar(select(ProductModel).where(ProductModel.model_id == model_id))
        if model is None:
            raise ModelNotFoundError(model_id)
        return model

    def _require_checkpoint(self, model_id: str, checkpoint_id: str) -> Checkpoint:
        statement = select(Checkpoint).where(
            Checkpoint.model_id == model_id,
            Checkpoint.checkpoint_id == checkpoint_id,
        )
        checkpoint = self.session.scalar(statement)
        if checkpoint is None:
            raise CheckpointNotFoundError(checkpoint_id)
        return checkpoint

    def _next_checkpoint_id(self, model_id: str) -> str:
        statement = select(Checkpoint.checkpoint_id).where(Checkpoint.model_id == model_id)
        highest = 0
        for checkpoint_id in self.session.scalars(statement):
            if checkpoint_id.startswith("ENG-") and checkpoint_id[4:].isdigit():
                highest = max(highest, int(checkpoint_id[4:]))
        return f"ENG-{highest + 1:03d}"
