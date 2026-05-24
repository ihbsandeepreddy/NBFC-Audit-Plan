import client from './client'
import type { AuditException } from '@/types'

export async function getExceptions(engagementId: string): Promise<AuditException[]> {
  const { data } = await client.get(`/engagements/${engagementId}/exceptions`)
  return data
}

export async function createException(
  engagementId: string,
  payload: Omit<AuditException, 'id' | 'engagement_id' | 'created_at'>
): Promise<AuditException> {
  const { data } = await client.post(`/engagements/${engagementId}/exceptions`, payload)
  return data
}

export async function updateException(
  engagementId: string,
  exceptionId: string,
  payload: Partial<AuditException>
): Promise<AuditException> {
  const { data } = await client.patch(`/engagements/${engagementId}/exceptions/${exceptionId}`, payload)
  return data
}

export async function deleteException(engagementId: string, exceptionId: string): Promise<void> {
  await client.delete(`/engagements/${engagementId}/exceptions/${exceptionId}`)
}

export async function exportExceptions(engagementId: string): Promise<Blob> {
  const { data } = await client.get(`/engagements/${engagementId}/exceptions/export`, {
    responseType: 'blob'
  })
  return data
}
