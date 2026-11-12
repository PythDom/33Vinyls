export type Kind = "collection" | "want";

export interface Release {
  id: number;
  master_id: number | null;
  artist: string;
  title: string;
  year: number | null;
  country: string;
  labels: { name: string; catno: string }[];
  formats: string[];
  barcodes: string[];
  matrix: string[];
  genres: string[];
  styles: string[];
  tracklist: { position: string; title: string; duration: string }[];
  notes: string;
  image: string;
  discogs_url: string;
  owned?: Kind[];
  friends?: FriendMark[];
  partial?: boolean;
}

export interface FriendMark {
  name: string;
  kind: Kind;
}

export interface ItemFields {
  media_grade?: string;
  sleeve_grade?: string;
  purchase_price?: number | null;
  purchase_date?: string;
  purchase_place?: string;
  notes?: string;
  location?: string;
  max_price?: number | null;
  added_at?: string;
}

export interface LocalItem {
  id: string;
  release_id: number;
  kind: Kind;
  fields: ItemFields;
  updated_at: string;
  deleted: 0 | 1;
  dirty: 0 | 1;
}

export interface PriceCard {
  release_id: number;
  currency: string;
  lowest: number | null;
  num_for_sale: number | null;
  suggested: Record<string, number>;
  low: number | null;
  median: number | null;
  high: number | null;
  source: string;
  fetched_at: string;
  note?: string | null;
  stale?: boolean;
}

export interface Candidate {
  id: number;
  master_id: number | null;
  artist?: string;
  title: string;
  year: number | null;
  country: string;
  label: string;
  catno: string;
  format: string;
  thumb: string;
  owned: Kind[];
  friends?: FriendMark[];
  score?: number;
  matched?: string[];
  image_score?: number;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
}

export const GRADES = ["M", "NM", "VG+", "VG", "G+", "G", "F", "P"] as const;
