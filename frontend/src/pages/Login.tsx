import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Layers, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import client from '@/api/client'
import { useAuthStore } from '@/stores/auth.store'
import type { User } from '@/types'

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type FormData = z.infer<typeof schema>

interface LoginResponse {
  access_token: string
  user: User
}

export function Login() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [showPwd, setShowPwd] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setApiError(null)
    try {
      const res = await client.post<LoginResponse>('/auth/login', {
        email: data.email,
        password: data.password,
      })
      setAuth(res.data.user, res.data.access_token)
      navigate('/')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosErr.response?.status === 401) {
        setApiError('Invalid email or password. Please try again.')
      } else {
        const msg = axiosErr.response?.data?.detail
        setApiError(msg ?? 'Unable to sign in. Please try again later.')
      }
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 to-primary-50 px-4">
      <div className="w-full max-w-sm">
        {/* Logo + heading */}
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-500 shadow-lg shadow-primary-500/25">
            <Layers className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
            NBFC Audit Intelligence
          </h1>
          <p className="mt-1.5 flex items-center gap-1.5 text-sm text-gray-500">
            <ShieldCheck className="h-3.5 w-3.5 text-primary-400" />
            Powered by real analytics
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-gray-200 bg-white px-8 py-8 shadow-sm">
          <h2 className="mb-6 text-base font-semibold text-gray-800">Sign in to your account</h2>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-sm font-medium text-gray-700"
              >
                Email address
              </label>
              <input
                id="email"
                {...register('email')}
                type="email"
                autoComplete="email"
                autoFocus
                placeholder="auditor@firm.com"
                className={[
                  'w-full rounded-lg border px-3.5 py-2.5 text-sm text-gray-900 outline-none transition-all',
                  'placeholder:text-gray-400',
                  errors.email
                    ? 'border-red-400 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100'
                    : 'border-gray-300 focus:border-primary-500 focus:ring-2 focus:ring-primary-100',
                ].join(' ')}
              />
              {errors.email && (
                <p className="mt-1.5 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-sm font-medium text-gray-700"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  {...register('password')}
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className={[
                    'w-full rounded-lg border px-3.5 py-2.5 pr-10 text-sm text-gray-900 outline-none transition-all',
                    'placeholder:text-gray-400',
                    errors.password
                      ? 'border-red-400 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100'
                      : 'border-gray-300 focus:border-primary-500 focus:ring-2 focus:ring-primary-100',
                  ].join(' ')}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
                  aria-label={showPwd ? 'Hide password' : 'Show password'}
                >
                  {showPwd ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1.5 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>

            {/* API error banner */}
            {apiError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {apiError}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      d="M12 3a9 9 0 1 0 9 9"
                    />
                  </svg>
                  Signing in…
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          NBFC Audit Intelligence Platform &copy; {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}

export default Login
