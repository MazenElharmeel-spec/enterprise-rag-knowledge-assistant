import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Login } from './Login'

describe('Login', () => {
  it('shows the demo account and labelled credential fields', () => {
    render(<Login onLogin={() => undefined} />)
    expect(screen.getByLabelText('Email address')).toBeTruthy()
    expect(screen.getByLabelText('Password')).toBeTruthy()
    expect(screen.getByText('alice@acme-demo.com / demo-pass-123')).toBeTruthy()
  })
})
