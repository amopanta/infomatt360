export type SessionProject = { id: string; name: string; role_id?: string | null; permissions?: string[] };
export type AuthSession = { user_id: string; full_name: string; email: string; must_change_password: boolean; projects: SessionProject[] };
