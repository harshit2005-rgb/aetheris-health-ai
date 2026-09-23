import { describe, it, expect, beforeEach } from 'vitest'
import { tokenStore } from './tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    tokenStore.clear()
  })

  it('starts with null tokens', () => {
    expect(tokenStore.getAccessToken()).toBeNull()
    expect(tokenStore.getRefreshToken()).toBeNull()
  })

  it('stores and retrieves access token', () => {
    tokenStore.setAccessToken('access-123')
    expect(tokenStore.getAccessToken()).toBe('access-123')
  })

  it('stores and retrieves refresh token', () => {
    tokenStore.setRefreshToken('refresh-456')
    expect(tokenStore.getRefreshToken()).toBe('refresh-456')
  })

  it('sets both tokens at once', () => {
    tokenStore.setTokens('access-1', 'refresh-1')
    expect(tokenStore.getAccessToken()).toBe('access-1')
    expect(tokenStore.getRefreshToken()).toBe('refresh-1')
  })

  it('clears both tokens', () => {
    tokenStore.setTokens('access-1', 'refresh-1')
    tokenStore.clear()
    expect(tokenStore.getAccessToken()).toBeNull()
    expect(tokenStore.getRefreshToken()).toBeNull()
  })

  it('sets access token to null', () => {
    tokenStore.setAccessToken('token')
    tokenStore.setAccessToken(null)
    expect(tokenStore.getAccessToken()).toBeNull()
  })

  it('sets refresh token to null', () => {
    tokenStore.setRefreshToken('token')
    tokenStore.setRefreshToken(null)
    expect(tokenStore.getRefreshToken()).toBeNull()
  })
})
