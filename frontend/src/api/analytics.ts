import client from './client'
import type { AnalyticsJob } from '@/types'

export async function uploadAnalyticsFile(
  engagementId: string,
  file: File,
  daRef: string
): Promise<AnalyticsJob> {
  const form = new FormData()
  form.append('file', file)
  form.append('da_ref', daRef)
  const { data } = await client.post(`/analytics/${engagementId}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function normalizeAnalyticsJob(
  engagementId: string,
  jobId: string,
  mapping: Record<string, string>
): Promise<AnalyticsJob> {
  const { data } = await client.post(`/analytics/${engagementId}/jobs/${jobId}/normalize`, { mapping })
  return data
}

export async function runAnalyticsJob(engagementId: string, jobId: string): Promise<AnalyticsJob> {
  const { data } = await client.post(`/analytics/${engagementId}/jobs/${jobId}/run`)
  return data
}

export async function getAnalyticsJobs(engagementId: string): Promise<AnalyticsJob[]> {
  const { data } = await client.get(`/analytics/${engagementId}/jobs`)
  return data
}

export async function getAnalyticsJob(engagementId: string, jobId: string): Promise<AnalyticsJob> {
  const { data } = await client.get(`/analytics/${engagementId}/jobs/${jobId}`)
  return data
}

export async function downloadAnalyticsResults(engagementId: string, jobId: string): Promise<Blob> {
  const { data } = await client.get(`/analytics/${engagementId}/jobs/${jobId}/download`, {
    responseType: 'blob'
  })
  return data
}

export async function runCreditPolicyValidation(
  engagementId: string,
  jobId: string
): Promise<AnalyticsJob> {
  const { data } = await client.post(`/analytics/${engagementId}/jobs/${jobId}/validate-policy`)
  return data
}
