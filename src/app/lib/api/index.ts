/**
 * API client for Datenschutzagent backend.
 *
 * Re-exports all domain modules. Consumers importing from "lib/api"
 * automatically resolve to this index file.
 *
 * Module breakdown:
 *   core.ts        – ApiError, token management, request helper, utilities
 *   admin.ts       – auth config, user profile, admin settings, webhooks
 *   cases.ts       – cases, run-checks, activities, DSB report, VVT, audit
 *   documents.ts   – documents, comments, app config
 *   findings.ts    – findings, comments, coverage preview
 *   playbooks.ts   – playbooks, legal bases, departments, VVT overview
 *   compliance.ts  – data breaches, DSR, AVV, TOM, templates, privacy policy
 */

export * from "./core";
export * from "./admin";
export * from "./cases";
export * from "./documents";
export * from "./findings";
export * from "./playbooks";
export * from "./compliance";
