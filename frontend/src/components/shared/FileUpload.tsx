import { useRef, useState, useCallback } from 'react'
import { Upload, X, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FileUploadProps {
  accept?: string
  multiple?: boolean
  onFiles: (files: File[]) => void
  maxSizeMB?: number
  className?: string
  label?: string
  hint?: string
  disabled?: boolean
}

export function FileUpload({
  accept = '.csv,.xlsx,.xls',
  multiple = false,
  onFiles,
  maxSizeMB = 50,
  className,
  label = 'Drop files here or click to upload',
  hint,
  disabled = false,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return
      const arr = Array.from(files)
      const oversized = arr.filter(f => f.size > maxSizeMB * 1024 * 1024)
      if (oversized.length > 0) {
        setError(`File exceeds ${maxSizeMB}MB limit: ${oversized.map(f => f.name).join(', ')}`)
        return
      }
      setError(null)
      setSelectedFiles(arr)
      onFiles(arr)
    },
    [maxSizeMB, onFiles]
  )

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (!disabled) handleFiles(e.dataTransfer.files)
  }

  const removeFile = (index: number) => {
    const updated = selectedFiles.filter((_, i) => i !== index)
    setSelectedFiles(updated)
    onFiles(updated)
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors',
          dragOver ? 'border-primary bg-primary-50' : 'border-gray-200 bg-gray-50 hover:border-gray-300 hover:bg-gray-100',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <Upload className="mb-3 h-8 w-8 text-gray-400" />
        <p className="text-sm font-medium text-gray-700">{label}</p>
        <p className="mt-1 text-xs text-gray-500">
          {hint ?? `${accept.replace(/\./g, '').toUpperCase()} up to ${maxSizeMB}MB`}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
          disabled={disabled}
        />
      </div>

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          {selectedFiles.map((file, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg border bg-white px-3 py-2">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-700">{file.name}</p>
                  <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <button
                onClick={() => removeFile(i)}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
