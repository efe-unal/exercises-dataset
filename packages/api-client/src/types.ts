/**
 * Types mirroring the API's responses.
 *
 * Kept by hand rather than generated, so the shape a client depends on is
 * visible in one file and a breaking API change shows up as a type error.
 */

export type Goal =
  | 'strength'
  | 'hypertrophy'
  | 'endurance'
  | 'fat_loss'
  | 'general_fitness';

export type Level = 'beginner' | 'intermediate' | 'advanced';

export type EquipmentProfile =
  | 'bodyweight'
  | 'home_minimal'
  | 'home_dumbbell'
  | 'full_gym';

export type Mechanic = 'compound' | 'isolation';
export type Role = 'primary' | 'accessory' | 'mobility';
export type Difficulty = Level;

/** What to do next for one exercise, derived from the athlete's own history. */
export type SuggestionAction = 'establish' | 'add_load' | 'repeat' | 'deload';

export interface Exercise {
  id: string;
  name: string;
  body_part: string;
  target: string;
  equipment: string;
  muscle_group?: string | null;
  secondary_muscles?: string[] | null;
  pattern: string;
  mechanic: Mechanic;
  role: Role;
  difficulty: Difficulty;
  image: string;
  gif_url: string;
  language?: string;
  instructions?: string | null;
  instruction_steps?: string[];
}

export interface ExerciseList {
  total: number;
  limit: number;
  offset: number;
  attribution: string;
  results: Exercise[];
}

export interface Facets {
  pattern: string[];
  role: string[];
  mechanic: string[];
  difficulty: string[];
  body_part: string[];
  target: string[];
  equipment: string[];
  equipment_profile: string[];
}

export interface Prescription {
  sets: number;
  rep_min: number;
  rep_max: number;
  rest_seconds: number;
  rir: number;
  tempo: string;
  /** Present on a week's copy of the plan; 1.0 except during a deload. */
  load_pct_of_baseline?: number;
}

export interface Suggestion {
  exercise_id: string;
  exercise_name?: string;
  action: SuggestionAction;
  weight_kg: number | null;
  rep_min: number;
  rep_max: number;
  reason: string;
  last_performed_at?: string | null;
  best_estimated_1rm?: number | null;
}

export interface PlanEntry {
  slot: string;
  exercise: Pick<
    Exercise,
    | 'id'
    | 'name'
    | 'body_part'
    | 'target'
    | 'equipment'
    | 'pattern'
    | 'mechanic'
    | 'role'
    | 'difficulty'
    | 'image'
    | 'gif_url'
  > & { attribution?: string | null };
  instructions: { language: string; text: string | null; steps: string[] };
  prescription: Prescription;
  load_step_kg: number;
  /** Only present on the next-session response. */
  suggestion?: Suggestion;
}

export interface PlanDay {
  name: string;
  estimated_minutes: number;
  exercises: PlanEntry[];
}

export interface PlanWeek {
  week: number;
  is_deload: boolean;
  guidance: string;
  days: PlanDay[];
  weekly_set_volume: Record<string, number>;
}

export interface ProgramProfile {
  goal: Goal;
  level: Level;
  days_per_week: number;
  equipment: EquipmentProfile | string[];
  session_minutes: number;
  weeks: number;
  language: string;
}

export interface Plan {
  profile: ProgramProfile;
  split: string;
  progression_model: string;
  weeks: PlanWeek[];
  attribution: string;
}

/** A saved plan, which additionally carries its identity in the account. */
export interface SavedPlan extends Plan {
  id: string;
  name: string;
  is_active?: boolean;
  created_at: string;
}

export interface ProgramSummary {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  goal: Goal;
  level: Level;
  days_per_week: number;
  weeks: number;
}

export interface ProgramRequest {
  goal?: Goal;
  level?: Level;
  days_per_week?: number;
  equipment?: EquipmentProfile | string[];
  session_minutes?: number;
  weeks?: number;
  language?: string;
  seed?: number | null;
  exclude_patterns?: string[];
}

export interface SaveProgramRequest extends ProgramRequest {
  name?: string;
  make_active?: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  language: string;
  unit_system: 'metric' | 'imperial';
  tier: 'free' | 'pro';
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface SetEntry {
  exercise_id: string;
  exercise_name: string;
  set_index: number;
  reps: number;
  weight_kg?: number | null;
  rir?: number | null;
  is_warmup?: boolean;
}

export interface LogSessionRequest {
  program_id: string;
  week: number;
  day_index: number;
  day_name: string;
  sets: SetEntry[];
  notes?: string | null;
  completed?: boolean;
}

export interface WorkoutSession {
  id: string;
  program_id: string;
  week: number;
  day_index: number;
  day_name: string;
  started_at: string;
  completed_at: string | null;
  notes: string | null;
  sets: Required<SetEntry>[];
}

/** The next unlogged day, with a load suggestion attached to each exercise. */
export type NextSession =
  | { program_id: string; complete: true; message: string }
  | {
      program_id: string;
      complete: false;
      week: number;
      day_index: number;
      is_deload: boolean;
      guidance: string;
      day: PlanDay;
      attribution: string;
    };

export interface ExerciseHistory {
  exercise_id: string;
  sets: Array<{
    performed_at: string;
    set_index: number;
    reps: number;
    weight_kg: number | null;
    rir: number | null;
    is_warmup: boolean;
    estimated_1rm: number | null;
  }>;
}

export interface Stats {
  total_sessions: number;
  total_working_sets: number;
  total_volume_kg: number;
  last_session_at: string | null;
}

export interface BodyMetric {
  metric: string;
  value: number;
  unit: string;
  recorded_at: string;
}
