import client from './client'
import type { CreditPolicy } from '@/types'

export async function getCreditPolicies(engagementId: string): Promise<CreditPolicy[]> {
  const { data } = await client.get(`/engagements/${engagementId}/credit-policies`)
  return data
}

export async function getCreditPolicy(engagementId: string, policyId: string): Promise<CreditPolicy> {
  const { data } = await client.get(`/engagements/${engagementId}/credit-policies/${policyId}`)
  return data
}

export async function createCreditPolicy(
  engagementId: string,
  payload: Omit<CreditPolicy, 'id'>
): Promise<CreditPolicy> {
  const { data } = await client.post(`/engagements/${engagementId}/credit-policies`, payload)
  return data
}

export async function updateCreditPolicy(
  engagementId: string,
  policyId: string,
  payload: Partial<CreditPolicy>
): Promise<CreditPolicy> {
  const { data } = await client.patch(`/engagements/${engagementId}/credit-policies/${policyId}`, payload)
  return data
}

export async function deleteCreditPolicy(engagementId: string, policyId: string): Promise<void> {
  await client.delete(`/engagements/${engagementId}/credit-policies/${policyId}`)
}
