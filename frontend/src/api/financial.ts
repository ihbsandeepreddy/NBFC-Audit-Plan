import client from './client'
import type { FinancialRatio } from '@/types'

export async function downloadFinancialTemplate(): Promise<Blob> {
  const { data } = await client.get('/financial/template', { responseType: 'blob' })
  return data
}

export async function uploadFinancialData(
  engagementId: string,
  file: File,
  period: string
): Promise<{ message: string; ratios: FinancialRatio[] }> {
  const form = new FormData()
  form.append('file', file)
  form.append('period', period)
  const { data } = await client.post(`/financial/${engagementId}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function getFinancialRatios(engagementId: string): Promise<{
  periods: string[]
  ratios: FinancialRatio[]
}> {
  const { data } = await client.get(`/financial/${engagementId}/ratios`)
  return data
}

export async function exportFinancialRatios(engagementId: string): Promise<Blob> {
  const { data } = await client.get(`/financial/${engagementId}/ratios/export`, {
    responseType: 'blob'
  })
  return data
}
