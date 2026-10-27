import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { InspectionState, MockCheckpointResult, MockInspectionResponse } from '../types/inspection'

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
  setImageBlob: (blob: Blob, name: string, source: LoadedImage['source']) => void
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

  useEffect(() => {
    return () => releaseObjectUrl()
  }, [releaseObjectUrl])

  const clearInspection = useCallback(() => {
    setInspection(null)
    setSelectedResult(null)
    setInspectionState('READY')
  }, [])

  const setImageBlob = useCallback((blob: Blob, name: string, source: LoadedImage['source']) => {
    releaseObjectUrl()
    const url = URL.createObjectURL(blob)
    objectUrlRef.current = url
    setImage({ url, name, source, size: blob.size, width: null, height: null })
    setError(null)
    clearInspection()
  }, [clearInspection, releaseObjectUrl])

  const handleReset = useCallback(() => {
    releaseObjectUrl()
    setImage(null)
    setError(null)
    setImageLoading(false)
    clearInspection()
  }, [clearInspection, releaseObjectUrl])

  const value: InspectionContextType = {
    image,
    setImage,
    setImageBlob,
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
