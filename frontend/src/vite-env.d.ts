/// <reference types="vite/client" />

declare module 'lucide-react' {
  import type { ComponentType, SVGProps } from 'react'

  export type LucideProps = SVGProps<SVGSVGElement> & {
    size?: number | string
    strokeWidth?: number | string
    className?: string
    color?: string
  }

  export type LucideIcon = ComponentType<LucideProps>

  export const Activity: LucideIcon
  export const Beaker: LucideIcon
  export const Binary: LucideIcon
  export const Boxes: LucideIcon
  export const Camera: LucideIcon
  export const ChartNoAxesCombined: LucideIcon
  export const CheckCircle2: LucideIcon
  export const CircleCheckBig: LucideIcon
  export const CircleDot: LucideIcon
  export const CircleX: LucideIcon
  export const ClipboardCheck: LucideIcon
  export const Clock3: LucideIcon
  export const Construction: LucideIcon
  export const Copy: LucideIcon
  export const Crosshair: LucideIcon
  export const Download: LucideIcon
  export const Droplets: LucideIcon
  export const Eye: LucideIcon
  export const FileChartColumn: LucideIcon
  export const FileImage: LucideIcon
  export const FileText: LucideIcon
  export const FlaskConical: LucideIcon
  export const Gauge: LucideIcon
  export const GitBranch: LucideIcon
  export const History: LucideIcon
  export const ImagePlus: LucideIcon
  export const Info: LucideIcon
  export const Menu: LucideIcon
  export const Network: LucideIcon
  export const Pencil: LucideIcon
  export const Play: LucideIcon
  export const Plus: LucideIcon
  export const Printer: LucideIcon
  export const RefreshCw: LucideIcon
  export const RotateCcw: LucideIcon
  export const Ruler: LucideIcon
  export const Save: LucideIcon
  export const Scan: LucideIcon
  export const ScanBarcode: LucideIcon
  export const ScanLine: LucideIcon
  export const ScanSearch: LucideIcon
  export const Search: LucideIcon
  export const Settings: LucideIcon
  export const SlidersHorizontal: LucideIcon
  export const Trash2: LucideIcon
  export const TriangleAlert: LucideIcon
  export const Video: LucideIcon
  export const X: LucideIcon
  export const ZoomIn: LucideIcon
  export const ZoomOut: LucideIcon
}
