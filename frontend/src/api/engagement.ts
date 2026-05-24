import client from './client'
import type { Engagement } from '@/types'

export async function getEngagements(): Promise<Engagement[]> {
  const { data } = await client.get('/engagements')
  return data
}

export async function getEngagement(id: string): Promise<Engagement> {
  const { data } = await client.get(`/engagements/${id}`)
  return data
}

export async function createEngagement(payload: Partial<Engagement>): Promise<Engagement> {
  const { data } = await client.post('/engagements', payload)
  return data
}

export async function updateEngagement(id: string, payload: Partial<Engagement>): Promise<Engagement> {
  const { data } = await client.patch(`/engagements/${id}`, payload)
  return data
}

export async function deleteEngagement(id: string): Promise<void> {
  await client.delete(`/engagements/${id}`)
}

export async function importEngagement(id: string, file: File): Promise<{ message: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post(`/engagements/${id}/import`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function exportEngagement(id: string): Promise<Blob> {
  const { data } = await client.get(`/engagements/${id}/export`, { responseType: 'blob' })
  return data
}

export async function loginUser(email: string, password: string): Promise<{ access_token: string; user: import('@/types').User }> {
  const form = new FormData()
  form.append('username', email)
  form.append('password', password)
  const { data } = await client.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
  return data
}

export async function getCurrentUser(): Promise<import('@/types').User> {
  const { data } = await client.get('/auth/me')
  return data
}
