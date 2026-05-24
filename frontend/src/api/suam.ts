import client from './client'
import type { SUAMEntry } from '@/types'

export async function getSUAMEntries(engagementId: string): Promise<SUAMEntry[]> {
  const { data } = await client.get(`/engagements/${engagementId}/suam`)
  return data
}

export async function createSUAMEntry(
  engagementId: string,
  payload: Omit<SUAMEntry, 'id' | 'engagement_id'>
): Promise<SUAMEntry> {
  const { data } = await client.post(`/engagements/${engagementId}/suam`, payload)
  return data
}

export async function updateSUAMEntry(
  engagementId: string,
  entryId: string,
  payload: Partial<SUAMEntry>
): Promise<SUAMEntry> {
  const { data } = await client.patch(`/engagements/${engagementId}/suam/${entryId}`, payload)
  return data
}

export async function deleteSUAMEntry(engagementId: string, entryId: string): Promise<void> {
  await client.delete(`/engagements/${engagementId}/suam/${entryId}`)
}

export async function getSUAMSummary(engagementId: string): Promise<{
  total_uncorrected: number
  total_corrected: number
  qualitative_count: number
  exceeds_pm: boolean
  exceeds_om: boolean
  opinion_recommendation: string
}> {
  const { data } = await client.get(`/engagements/${engagementId}/suam/summary`)
  return data
}
