export type ModuleStatus = "operativo" | "parcial" | "en_desarrollo";

export interface Capability { key: string; description: string; implemented: boolean }

export interface ModuleInfo {
  key: string; name: string; version: string; description: string; status: ModuleStatus;
  capabilities: Capability[]; dependencies: string[]; inputs: string[]; outputs: string[];
  possible_errors: string[]; limitations: string[]; implemented_count: number; api_prefix: string | null;
}

export interface User { id: string; username: string; full_name: string; role_key: "admin" | "analista" | "lector"; is_active: boolean }

export interface DataRecord {
  id: string; data_type: string; title: string; source_name: string; latitude: number | null; longitude: number | null;
  bbox: number[] | null; observed_at: string | null; received_at: string; unit: string; value: number | null;
  file_format: string; validation_status: string; validation_messages: string[]; quality: string; provenance: string;
  is_simulated: boolean; file_size: number | null; sha256: string | null; extra: Record<string, unknown>;
}

export interface Followup { id: string; note: string; new_status: string | null; created_at: string }

export interface Alert {
  id: string; title: string; description: string; module_key: string; level: "bajo" | "medio" | "alto";
  alert_kind: string; latitude: number | null; longitude: number | null; evidence: string; source_name: string;
  observed_at: string | null; uncertainty: string; validation_status: string; is_simulated: boolean;
  created_at: string; followups: Followup[];
}

export interface Layer {
  record_id: string; title: string; data_type: string; is_simulated: boolean; source: string;
  geojson: GeoJSON.FeatureCollection;
}

export interface Dashboard {
  alerts: { total: number; by_level: Record<string, number>; by_status: Record<string, number> };
  records: { total: number; by_type: Record<string, number>; simulated: number; real: number };
  recent_activity: { at: string; action: string; target_type: string; success: boolean }[];
  sources: { name: string; kind: string; license: string }[];
  modules: { key: string; name: string; status: ModuleStatus }[];
  processing: { queued_jobs: number; note: string };
}

export interface AIModel {
  id: string; name: string; module_key: string; algorithm: string; version: string; status: string;
  metrics: Record<string, unknown>; dataset_description: string; created_at: string;
}

export interface ReportItem { id: string; title: string; module_key: string; created_at: string; content_md: string }
