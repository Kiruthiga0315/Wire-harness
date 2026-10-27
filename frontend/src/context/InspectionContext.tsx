import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { InspectionState, MockCheckpointResult, MockInspectionResponse } from '../types/inspection'
import { ACTIVE_IMAGE_URL, getActiveImageMetadata, resetActiveImage, uploadActiveImage } from '../services/api'

export interface LoadedImage {
  url: string
  name: string
  source: 'demo' | 'upload'
  size: number
  width: number | null
  height: number | null
}

interface InspectionContextType {
  image: LoadedImage | null
  setImage: React.Dispatch<React.SetStateAction<LoadedImage | null>>
  setImageBlob: (blob: Blob, name: string, source: LoadedImage['source']) => Promise<void>
  uploadActiveImageFile: (file: File) => Promise<void>
  reloadActiveImage: () => Promise<void>
  syncingActiveImage: boolean
  activeVersion: number
  imageLoading: boolean
  setImageLoading: React.Dispatch<React.SetStateAction<boolean>>
  inspectionState: InspectionState
  setInspectionState: React.Dispatch<React.SetStateAction<InspectionState>>
  inspection: MockInspectionResponse | null
  setInspection: React.Dispatch<React.SetStateAction<MockInspectionResponse | null>>
  selectedResult: MockCheckpointResult | null
  setSelectedResult: React.Dispatch<React.SetStateAction<MockCheckpointResult | null>>
  error: string | null
  setError: React.Dispatch<React.SetStateAction<string | null>>
  clearInspection: () => void
  handleReset: () => void
}

const InspectionContext = createContext<InspectionContextType | undefined>(undefined)

export function InspectionProvider({ children }: { children: React.ReactNode }) {
  const objectUrlRef = useRef<string | null>(null)
  const [image, setImage] = useState<LoadedImage | null>(null)
  const [imageLoading, setImageLoading] = useState(false)
  const [syncingActiveImage, setSyncingActiveImage] = useState(false)
  const [activeVersion, setActiveVersion] = useState(1)
  const [inspectionState, setInspectionState] = useState<InspectionState>('READY')
  const [inspection, setInspection] = useState<MockInspectionResponse | null>(null)
  const [selectedResult, setSelectedResult] = useState<MockCheckpointResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const releaseObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
  }, [])

  const reloadActiveImage = useCallback(async () => {
    try {
      const meta = await getActiveImageMetadata()
      if (meta) {
        const version = Date.now()
        setImage({
          url: `${ACTIVE_IMAGE_URL}?v=${version}`,
          name: meta.filename,
          source: meta.source,
          size: meta.size,
          width: meta.width,
          height: meta.height,
        })
        setActiveVersion(version)
      }
    } catch {
      // Silently ignore initialization error
    }
  }, [])

  useEffect(() => {
    void reloadActiveImage()
  }, [reloadActiveImage])

  useEffect(() => {
    return () => releaseObjectUrl()
  }, [releaseObjectUrl])

  const clearInspection = useCallback(() => {
    setInspection(null)
    setSelectedResult(null)
    setInspectionState('READY')
  }, [])

  const setImageBlob = useCallback(async (blob: Blob, name: string, source: LoadedImage['source']) => {
    releaseObjectUrl()
    const localUrl = URL.createObjectURL(blob)
    objectUrlRef.current = localUrl
    setImage({ url: localUrl, name, source, size: blob.size, width: null, height: null })
    setError(null)
    clearInspection()
    setSyncingActiveImage(true)

    try {
      if (source === 'upload') {
        const meta = await uploadActiveImage(blob, name)
        const version = Date.now()
        setImage({
          url: `${ACTIVE_IMAGE_URL}?v=${version}`,
          name: meta.filename,
          source: 'upload',
          size: meta.size,
          width: meta.width,
          height: meta.height,
        })
        setActiveVersion(version)
      } else {
        await resetActiveImage()
        const meta = await getActiveImageMetadata()
        const version = Date.now()
        setImage({
          url: `${ACTIVE_IMAGE_URL}?v=${version}`,
          name: meta?.filename ?? name,
          source: 'demo',
          size: meta?.size ?? blob.size,
          width: meta?.width ?? null,
          height: meta?.height ?? null,
        })
        setActiveVersion(version)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync image to backend.')
    } finally {
      setSyncingActiveImage(false)
    }
  }, [clearInspection, releaseObjectUrl])

  const uploadActiveImageFile = useCallback(async (file: File) => {
    await setImageBlob(file, file.name, 'upload')
  }, [setImageBlob])

  const handleReset = useCallback(() => {
    releaseObjectUrl()
    setImage(null)
    setError(null)
    setImageLoading(false)
    clearInspection()
    setSyncingActiveImage(true)
    void resetActiveImage()
      .then(() => reloadActiveImage())
      .finally(() => setSyncingActiveImage(false))
  }, [clearInspection, releaseObjectUrl, reloadActiveImage])

  const value: InspectionContextType = {
    image,
    setImage,
    setImageBlob,
    uploadActiveImageFile,
    reloadActiveImage,
    syncingActiveImage,
    activeVersion,
    imageLoading,
    setImageLoading,
    inspectionState,
    setInspectionState,
    inspection,
    setInspection,
    selectedResult,
    setSelectedResult,
    error,
    setError,
    clearInspection,
    handleReset,
  }

  return (
    <InspectionContext.Provider value={value}>
      {children}
    </InspectionContext.Provider>
  )
}

export function useInspection(): InspectionContextType {
  const context = useContext(InspectionContext)
  if (!context) {
    throw new Error('useInspection must be used within an InspectionProvider')
  }
  return context
}
