export interface User {
  id: number;
  email: string;
  username: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Repository {
  id: number;
  github_repo_id: number;
  full_name: string;
  name: string;
  owner: string;
  description: string | null;
  html_url: string;
  language: string | null;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  last_synced_at: string | null;
  created_at: string;
  stored_issues_count?: number;
}

export interface IssueLabel {
  name: string;
  color?: string;
  description?: string;
}

export interface Issue {
  id: number;
  repository_id: number;
  github_issue_id: number;
  issue_number: number;
  title: string;
  body: string | null;
  state: "open" | "closed" | string;
  author: string | null;
  labels: (IssueLabel | string)[];
  comments_count: number;
  html_url: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface PaginatedIssues {
  items: Issue[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PullRequest {
  id: number;
  repository_id: number;
  github_pr_id: number;
  pr_number: number;
  title: string;
  body: string | null;
  state: "open" | "closed" | "merged" | string;
  is_merged: boolean;
  merged_at: string | null;
  author: string | null;
  labels: (IssueLabel | string)[];
  html_url: string;
  diff_url: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface PaginatedPullRequests {
  items: PullRequest[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface IngestionJob {
  id: number;
  repository_id: number | null;
  repository_name: string;
  status: "pending" | "running" | "completed" | "failed";
  total_issues_ingested: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface IngestAcceptedResponse {
  message: string;
  job_id: number;
  status: string;
  repository_name: string;
}

export interface ActionRecommendation {
  id: number;
  issue_id: number;
  action_type: string;
  action_title: string;
  rationale: string;
  severity: "critical" | "warning" | "info" | string;
  created_at: string;
}

export interface IssueAnalysis {
  id: number;
  issue_id: number;
  category: "bug" | "feature_request" | "improvement" | "question" | "documentation" | string;
  priority: "P0_CRITICAL" | "P1_HIGH" | "P2_MEDIUM" | "P3_LOW" | string;
  confidence: number;
  model_version: string;
  root_cause_hypothesis: string | null;
  error_type: string | null;
  stack_trace_detected: boolean;
  reproduction_steps_detected: boolean;
  extracted_stack_trace: string | null;
  affected_components: string[];
  fix_target_file: string | null;
  proposed_code_patch: string | null;
  verification_test_code: string | null;
  patch_explanation: string | null;
  analyzed_at: string;
  recommendations: ActionRecommendation[];
}

export interface Commit {
  id: number;
  repository_id: number;
  pull_request_id: number | null;
  sha: string;
  message: string;
  author_name: string | null;
  author_email: string | null;
  committed_at: string | null;
  html_url: string | null;
  created_at: string;
}

export interface CodeDiff {
  id: number;
  repository_id: number;
  pull_request_id: number;
  commit_sha: string | null;
  filename: string;
  previous_filename: string | null;
  status: "added" | "modified" | "removed" | "renamed" | string;
  additions: number;
  deletions: number;
  changes_count: number;
  diff_content: string | null;
  raw_url: string | null;
  created_at: string;
}

export interface ResolvedIssueSummary {
  id: number;
  issue_number: number;
  title: string;
  state: string;
  html_url: string;
}

export interface PullRequestChanges {
  pr_id: number;
  pr_number: number;
  total_commits: number;
  total_files_changed: number;
  total_additions: number;
  total_deletions: number;
  resolved_issues: ResolvedIssueSummary[];
  commits: Commit[];
  files: CodeDiff[];
}

// Global Search & Command Palette (Phase 1)
export interface SearchResultRepository {
  id: number;
  type: "repository";
  name: string;
  owner: string;
  full_name: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  open_issues_count: number;
}

export interface SearchResultIssue {
  id: number;
  type: "issue";
  repository_id: number;
  repository_name: string;
  issue_number: number;
  title: string;
  state: string;
  comments_count: number;
  labels: (IssueLabel | string | { name: string; color?: string })[];
}

export interface SearchResultPullRequest {
  id: number;
  type: "pull_request";
  repository_id: number;
  repository_name: string;
  pr_number: number;
  title: string;
  state: string;
  is_merged: boolean;
  author: string | null;
  created_at: string | null;
}

// Phase 2: Semantic Code Search & AI Intelligence
export interface SearchResultCodeChunk {
  id: number;
  type: "code_chunk";
  repository_id: number;
  repository_name: string;
  file_path: string;
  language: string;
  start_line: number;
  end_line: number;
  content: string;
  relevance_score: number;
}

export interface SearchResultInvestigation {
  id: number;
  type: "investigation";
  issue_id: number;
  issue_number: number;
  issue_title: string;
  repository_id: number;
  repository_name: string;
  priority: string | null;
  error_type: string;
  root_cause_hypothesis: string;
  fix_target_file: string | null;
  confidence: number | null;
  analyzed_at: string | null;
}

export interface CodeCitation {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  relevance: number;
}

export interface AIExplanationResponse {
  query: string;
  answer: string;
  evidence_sufficient: boolean;
  citations: CodeCitation[];
  retrieved_chunks_count: number;
}

export interface CodeIndexStatus {
  repository_id: number;
  status: "not_indexed" | "indexing" | "ready" | "failed" | string;
  total_files: number;
  indexed_chunks: number;
  last_indexed_at: string | null;
  error_message: string | null;
}

export type SearchMode = "all" | "code" | "investigations" | "keyword";

export interface GlobalSearchResponse {
  query: string;
  mode?: SearchMode | string;
  total: number;
  repositories: SearchResultRepository[];
  issues: SearchResultIssue[];
  pull_requests: SearchResultPullRequest[];
  code_chunks?: SearchResultCodeChunk[];
  investigations?: SearchResultInvestigation[];
}

