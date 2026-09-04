/**
 * The API client, shared by the web app and any future mobile app.
 *
 * Deliberately free of framework and platform assumptions: it uses `fetch`
 * and an injected token store, so the same file runs in a browser, in React
 * Native, and in Node. Nothing here imports React.
 */

import type {
  AuthToken,
  BodyMetric,
  Exercise,
  ExerciseHistory,
  ExerciseList,
  Facets,
  LogSessionRequest,
  NextSession,
  Plan,
  ProgramRequest,
  ProgramSummary,
  SaveProgramRequest,
  SavedPlan,
  Stats,
  Suggestion,
  User,
  WorkoutSession,
} from './types.js';

/** Where the session token is kept. Async so React Native's storage fits. */
export interface TokenStore {
  get(): string | null | Promise<string | null>;
  set(token: string | null): void | Promise<void>;
}

/** Keeps the token in memory only — the default, and the safe fallback. */
export class MemoryTokenStore implements TokenStore {
  private token: string | null = null;
  get() {
    return this.token;
  }
  set(token: string | null) {
    this.token = token;
  }
}

/**
 * Persists the token in `localStorage`.
 *
 * Every accessor is guarded: private-mode browsers and blocked site data make
 * these throw rather than return empty, and a thrown storage error must never
 * take down a signed-in session.
 */
export class LocalStorageTokenStore implements TokenStore {
  constructor(private readonly key = 'exercises.token') {}

  get(): string | null {
    try {
      return globalThis.localStorage?.getItem(this.key) ?? null;
    } catch {
      return null;
    }
  }

  set(token: string | null): void {
    try {
      if (token === null) globalThis.localStorage?.removeItem(this.key);
      else globalThis.localStorage?.setItem(this.key, token);
    } catch {
      /* storage unavailable — the session simply does not survive a reload */
    }
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** The caller is not signed in, or their token expired. */
  get isUnauthorized() {
    return this.status === 401;
  }

  /** The account's tier does not include this feature. */
  get isPaymentRequired() {
    return this.status === 402;
  }

  get isRateLimited() {
    return this.status === 429;
  }
}

export interface ClientOptions {
  baseUrl: string;
  /** For the developer-facing catalog product; not needed by the apps. */
  apiKey?: string;
  tokenStore?: TokenStore;
  /** Injectable so tests and React Native can supply their own. */
  fetch?: typeof fetch;
  /** Called whenever a request comes back 401, so the UI can sign out. */
  onUnauthorized?: () => void;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: boolean;
}

export class ExercisesClient {
  readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly tokens: TokenStore;
  private readonly fetchImpl: typeof fetch;
  private readonly onUnauthorized?: () => void;

  constructor(options: ClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.apiKey = options.apiKey;
    this.tokens = options.tokenStore ?? new MemoryTokenStore();
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.onUnauthorized = options.onUnauthorized;
  }

  // --- plumbing -------------------------------------------------------
  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, query, auth = false } = options;

    const url = new URL(this.baseUrl + path);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }

    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (this.apiKey) headers['X-API-Key'] = this.apiKey;
    if (auth) {
      const token = await this.tokens.get();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await this.fetchImpl(url.toString(), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    const parsed = text ? safeParse(text) : undefined;

    if (!response.ok) {
      if (response.status === 401) {
        await this.tokens.set(null);
        this.onUnauthorized?.();
      }
      throw new ApiError(response.status, detailOf(parsed) ?? response.statusText, parsed);
    }
    return parsed as T;
  }

  /** Whether a token is present. Not proof it is still valid. */
  async isSignedIn(): Promise<boolean> {
    return (await this.tokens.get()) !== null;
  }

  // --- accounts -------------------------------------------------------
  async register(input: {
    email: string;
    password: string;
    display_name?: string;
    language?: string;
  }): Promise<AuthToken> {
    const token = await this.request<AuthToken>('/v1/auth/register', {
      method: 'POST',
      body: input,
    });
    await this.tokens.set(token.access_token);
    return token;
  }

  async login(email: string, password: string): Promise<AuthToken> {
    const token = await this.request<AuthToken>('/v1/auth/login', {
      method: 'POST',
      body: { email, password },
    });
    await this.tokens.set(token.access_token);
    return token;
  }

  async logout(): Promise<void> {
    try {
      await this.request<void>('/v1/auth/logout', { method: 'POST', auth: true });
    } finally {
      // Whatever the server said, the local session is over.
      await this.tokens.set(null);
    }
  }

  /** Ask for a reset link. Succeeds whether or not the address has an account. */
  requestPasswordReset(email: string): Promise<{ detail: string }> {
    return this.request('/v1/auth/password-reset/request', {
      method: 'POST',
      body: { email },
    });
  }

  /** Set a new password from a reset link. Signs every device out. */
  async confirmPasswordReset(token: string, password: string): Promise<void> {
    await this.request<void>('/v1/auth/password-reset/confirm', {
      method: 'POST',
      body: { token, password },
    });
    // The server has just invalidated every session, this device's included.
    // Holding on to the old token would leave the app looking signed in until
    // the next request failed.
    await this.tokens.set(null);
  }

  me(): Promise<User> {
    return this.request<User>('/v1/auth/me', { auth: true });
  }

  updateMe(changes: {
    display_name?: string;
    language?: string;
    unit_system?: 'metric' | 'imperial';
  }): Promise<User> {
    return this.request<User>('/v1/auth/me', {
      method: 'PATCH',
      body: changes,
      auth: true,
    });
  }

  // --- catalog --------------------------------------------------------
  facets(): Promise<Facets> {
    return this.request<Facets>('/v1/facets');
  }

  exercises(filters: {
    pattern?: string;
    role?: string;
    mechanic?: string;
    body_part?: string;
    target?: string;
    difficulty?: string;
    equipment_profile?: string;
    q?: string;
    language?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<ExerciseList> {
    return this.request<ExerciseList>('/v1/exercises', { query: filters });
  }

  exercise(id: string, language = 'en'): Promise<Exercise> {
    return this.request<Exercise>(`/v1/exercises/${encodeURIComponent(id)}`, {
      query: { language },
    });
  }

  /** Movements that can stand in for this one when it is unavailable. */
  alternatives(
    exerciseId: string,
    options: {
      equipment_profile?: string;
      difficulty?: string;
      language?: string;
      limit?: number;
    } = {},
  ): Promise<{
    exercise_id: string;
    pattern: string;
    mechanic: string;
    attribution: string;
    alternatives: Exercise[];
  }> {
    return this.request(
      `/v1/exercises/${encodeURIComponent(exerciseId)}/alternatives`,
      { query: options },
    );
  }

  /** Absolute URL for a media path returned by the API. */
  mediaUrl(path: string): string {
    if (/^https?:\/\//.test(path)) return path;
    return `${this.baseUrl}/${path.replace(/^\/+/, '')}`;
  }

  // --- programs -------------------------------------------------------
  /** Generate a block without an account — what a visitor sees first. */
  previewProgram(request: ProgramRequest): Promise<Plan> {
    return this.request<Plan>('/v1/programs/preview', {
      method: 'POST',
      body: request,
    });
  }

  saveProgram(request: SaveProgramRequest): Promise<ProgramSummary> {
    return this.request<ProgramSummary>('/v1/programs', {
      method: 'POST',
      body: request,
      auth: true,
    });
  }

  listPrograms(): Promise<ProgramSummary[]> {
    return this.request<ProgramSummary[]>('/v1/programs', { auth: true });
  }

  activeProgram(): Promise<SavedPlan> {
    return this.request<SavedPlan>('/v1/programs/active', { auth: true });
  }

  program(id: string): Promise<SavedPlan> {
    return this.request<SavedPlan>(`/v1/programs/${encodeURIComponent(id)}`, {
      auth: true,
    });
  }

  activateProgram(id: string): Promise<ProgramSummary> {
    return this.request<ProgramSummary>(
      `/v1/programs/${encodeURIComponent(id)}/activate`,
      { method: 'POST', auth: true },
    );
  }

  deleteProgram(id: string): Promise<void> {
    return this.request<void>(`/v1/programs/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      auth: true,
    });
  }

  // --- workouts -------------------------------------------------------
  logSession(request: LogSessionRequest): Promise<WorkoutSession> {
    return this.request<WorkoutSession>('/v1/workouts/sessions', {
      method: 'POST',
      body: request,
      auth: true,
    });
  }

  listSessions(
    filters: { program_id?: string; limit?: number; offset?: number } = {},
  ): Promise<WorkoutSession[]> {
    return this.request<WorkoutSession[]>('/v1/workouts/sessions', {
      query: filters,
      auth: true,
    });
  }

  deleteSession(id: string): Promise<void> {
    return this.request<void>(`/v1/workouts/sessions/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      auth: true,
    });
  }

  /** The next unlogged day, with a load suggestion per exercise. */
  nextSession(programId: string): Promise<NextSession> {
    return this.request<NextSession>(
      `/v1/workouts/next/${encodeURIComponent(programId)}`,
      { auth: true },
    );
  }

  suggestion(exerciseId: string, repMin = 8, repMax = 12): Promise<Suggestion> {
    return this.request<Suggestion>(
      `/v1/workouts/suggestion/${encodeURIComponent(exerciseId)}`,
      { query: { rep_min: repMin, rep_max: repMax }, auth: true },
    );
  }

  exerciseHistory(exerciseId: string, limit = 50): Promise<ExerciseHistory> {
    return this.request<ExerciseHistory>(
      `/v1/workouts/history/${encodeURIComponent(exerciseId)}`,
      { query: { limit }, auth: true },
    );
  }

  stats(): Promise<Stats> {
    return this.request<Stats>('/v1/workouts/stats', { auth: true });
  }

  recordMetric(metric: {
    metric: string;
    value: number;
    unit: string;
    recorded_at?: string;
  }): Promise<{ id: string; recorded_at: string }> {
    return this.request('/v1/workouts/metrics', {
      method: 'POST',
      body: metric,
      auth: true,
    });
  }

  metrics(metric?: string, limit = 100): Promise<BodyMetric[]> {
    return this.request<BodyMetric[]>('/v1/workouts/metrics', {
      query: { metric, limit },
      auth: true,
    });
  }
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** FastAPI reports errors as `{detail: ...}`; unwrap it for the message. */
function detailOf(body: unknown): string | undefined {
  if (typeof body !== 'object' || body === null) return undefined;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    // Validation errors arrive as a list of per-field objects.
    const messages = detail
      .map((item) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter((message): message is string => message !== null);
    if (messages.length) return messages.join('; ');
  }
  return undefined;
}
