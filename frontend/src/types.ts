export type DataStatus = 'visible' | 'partially_readable' | 'unreadable' | 'not_found_in_image' | 'unknown';
export type ImageQuality = 'clear' | 'limited' | 'unreadable' | 'unknown';
export type ImageIssue = 'blurry' | 'partially_obscured' | 'curved_surface' | 'glare' | 'low_resolution' | 'cropped' | 'low_contrast' | 'perspective_distortion' | 'other';
export type FindingStatus = 'conflict_detected' | 'potential_conflict' | 'no_conflict_found' | 'unknown' | 'insufficient_information';
export type Evidence = { source_text: string; field: string; explanation: string };
export type Finding = {
  preference: string; status: FindingStatus; severity: 'high' | 'medium' | 'low' | 'informational';
  summary: string; evidence: Evidence[]; reasoning_type: string; uncertainty?: string | null;
};
export type LabelField = { value?: string | null; source_text?: string | null; status: DataStatus; confidence?: number | null };
export type Ingredient = { name: string; source_text: string; normalized_name?: string | null; status: DataStatus; confidence?: number | null };
export type NutritionFact = { nutrient: string; value?: number | null; unit?: string | null; basis?: string | null; source_text?: string | null; status: DataStatus };
export type LabelData = {
  image_quality: ImageQuality; image_issues: ImageIssue[];
  product_name: LabelField; ingredients: Ingredient[]; ingredients_status: DataStatus;
  allergen_statement: LabelField; nutrition: NutritionFact[]; serving_size: LabelField;
  dietary_claims: LabelField[]; certifications: LabelField[]; other_visible_text: string[];
  unreadable_regions: string[]; extraction_warnings: string[]; full_text: string;
};
export type DietaryProfile = {
  allergens: string[]; avoid_ingredients: string[]; dietary_patterns: string[];
  nutrition_thresholds: { nutrient: string; direction: string; value: number; unit: string; basis: string }[];
  avoid_palm_oil: boolean; avoid_artificial_sweeteners: boolean; custom_requirements: string[];
};
export type AnalysisResponse = { label: LabelData; findings: Finding[]; warnings: string[] };
