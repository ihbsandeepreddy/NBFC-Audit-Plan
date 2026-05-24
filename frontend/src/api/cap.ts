import client from './client'
import type { CAPProcedure } from '@/types'

export async function getCAPProcedures(engagementId: string): Promise<CAPProcedure[]> {
  const { data } = await client.get(`/cap/${engagementId}/procedures`)
  return data
}

export async function updateCAPProcedure(
  engagementId: string,
  procId: string,
  payload: Partial<CAPProcedure>
): Promise<CAPProcedure> {
  const { data } = await client.patch(`/cap/${engagementId}/procedures/${procId}`, payload)
  return data
}

export async function bulkUpdateCAPProcedures(
  engagementId: string,
  updates: Array<{ id: string } & Partial<CAPProcedure>>
): Promise<CAPProcedure[]> {
  const { data } = await client.patch(`/cap/${engagementId}/procedures/bulk`, updates)
  return data
}

export async function getCAPStats(engagementId: string): Promise<{
  total: number
  completed: number
  in_progress: number
  pending: number
  exceptions: number
  by_phase: Record<string, { total: number; completed: number }>
}> {
  const { data } = await client.get(`/cap/${engagementId}/stats`)
  return data
}
