/** Typed to match backend/app/schemas/chat_schema.py exactly. */
import { api } from './api'

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: number
  role: ChatRole
  content: string
  is_mock_response: boolean
  created_at: string
}

export interface ToolTrace {
  tool: string
  label: string
}

export interface ProposedAction {
  token: string
  kind: string
  summary: string
}

export interface ChatSendResponse {
  session_id: number
  reply: ChatMessage
  is_mock: boolean
  tool_trace: ToolTrace[]
  proposed_actions: ProposedAction[]
}

/** Carries out an action the assistant proposed. Only call this from a
 * button the user pressed. */
export async function confirmAgentAction(token: string): Promise<string> {
  const { data } = await api.post<{ message: string }>('/chat/actions/confirm', { token })
  return data.message
}

export interface ChatSession {
  id: number
  title: string | null
  created_at: string
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[]
}

export async function sendChatMessage(
  message: string,
  sessionId?: number,
  useProfile = true,
): Promise<ChatSendResponse> {
  // The backend may wait on a slow provider, then a fallback, plus tool
  // calls - well past the default 15s client timeout.
  const { data } = await api.post<ChatSendResponse>(
    '/chat',
    { message, session_id: sessionId ?? null, use_profile: useProfile },
    { timeout: 90000 },
  )
  return data
}

export async function listChatSessions(): Promise<ChatSession[]> {
  const { data } = await api.get<ChatSession[]>('/chat/sessions')
  return data
}

export async function getChatSession(id: number): Promise<ChatSessionDetail> {
  const { data } = await api.get<ChatSessionDetail>(`/chat/sessions/${id}`)
  return data
}

export async function deleteChatSession(id: number): Promise<void> {
  await api.delete(`/chat/sessions/${id}`)
}
