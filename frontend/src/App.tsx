import { useEffect, useRef, useState } from 'react';
import { AlertCircle, AlertTriangle, ArrowRight, Check, ChevronDown, CircleHelp, FileImage, Leaf, LoaderCircle, RotateCcw, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { analyzeImage, compareLabel, validateImage } from './services/api';
import type { AnalysisResponse, DietaryProfile, Finding, FindingStatus, LabelData } from './types';

const emptyProfile: DietaryProfile = {
  allergens: [], avoid_ingredients: [], dietary_patterns: [], nutrition_thresholds: [],
  avoid_palm_oil: false, avoid_artificial_sweeteners: false, custom_requirements: [],
};
const storedProfileSchema = z.object({
  allergens: z.array(z.string()).default([]),
  avoid_ingredients: z.array(z.string()).default([]),
  dietary_patterns: z.array(z.string()).default([]),
  nutrition_thresholds: z.array(z.object({ nutrient: z.string(), direction: z.enum(['maximum', 'minimum']), value: z.number().nonnegative(), unit: z.string(), basis: z.string() })).default([]),
  avoid_palm_oil: z.boolean().default(false),
  avoid_artificial_sweeteners: z.boolean().default(false),
  custom_requirements: z.array(z.string()).default([]),
});

function loadSavedProfile(): DietaryProfile {
  try {
    const saved = localStorage.getItem('labellens-profile');
    if (!saved) return emptyProfile;
    const parsed = storedProfileSchema.safeParse(JSON.parse(saved));
    return parsed.success ? parsed.data : emptyProfile;
  } catch { return emptyProfile; }
}

function hasSavedProfile() {
  try { return Boolean(localStorage.getItem('labellens-profile')); }
  catch { return false; }
}

const allergenOptions = ['Peanuts', 'Tree nuts', 'Milk', 'Eggs', 'Soy', 'Wheat', 'Fish', 'Crustaceans', 'Sesame', 'Gluten'];
const patternOptions = ['Vegetarian', 'Vegan', 'Jain', 'Halal', 'Kosher'];
const nutrients = [
  { nutrient: 'Sugar', direction: 'maximum', unit: 'g' },
  { nutrient: 'Sodium', direction: 'maximum', unit: 'mg' },
  { nutrient: 'Protein', direction: 'minimum', unit: 'g' },
  { nutrient: 'Saturated fat', direction: 'maximum', unit: 'g' },
];
const statusLabels: Record<FindingStatus, string> = {
  conflict_detected: 'Conflict detected', potential_conflict: 'Potential conflict',
  no_conflict_found: 'No match found', unknown: 'Unknown', insufficient_information: 'Insufficient information',
};
const customTermSchema = z.object({ value: z.string().trim().min(1, 'Enter a preference.').max(80, 'Use 80 characters or fewer.') });

function toggle(values: string[], item: string) {
  return values.includes(item) ? values.filter((value) => value !== item) : [...values, item];
}

function App() {
  const [profile, setProfile] = useState<DietaryProfile>(loadSavedProfile);
  const [rememberProfile, setRememberProfile] = useState(hasSavedProfile);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const avoidForm = useForm<{ value: string }>({ resolver: zodResolver(customTermSchema), defaultValues: { value: '' } });
  const patternForm = useForm<{ value: string }>({ resolver: zodResolver(customTermSchema), defaultValues: { value: '' } });
  const [customNutrient, setCustomNutrient] = useState('');
  const [customNutrientValue, setCustomNutrientValue] = useState('');
  const [customNutrientDirection, setCustomNutrientDirection] = useState('maximum');
  const [customNutrientUnit, setCustomNutrientUnit] = useState('g');
  const [editedIngredients, setEditedIngredients] = useState('');
  const [editedIngredientsStatus, setEditedIngredientsStatus] = useState<LabelData['ingredients_status']>('unknown');
  const [editedNutrition, setEditedNutrition] = useState('');
  const [editedAllergen, setEditedAllergen] = useState('');
  const [editedAllergenStatus, setEditedAllergenStatus] = useState<LabelData['allergen_statement']['status']>('unknown');
  const [editedText, setEditedText] = useState('');
  const [correctionError, setCorrectionError] = useState('');
  const [editingExtraction, setEditingExtraction] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState('');
  const [providerStatus, setProviderStatus] = useState<'checking' | 'ready' | 'configuration_required' | 'offline'>('checking');
  const [maxUploadMB, setMaxUploadMB] = useState(10);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    try {
      if (rememberProfile) localStorage.setItem('labellens-profile', JSON.stringify(profile));
      else localStorage.removeItem('labellens-profile');
    } catch {}
  }, [profile, rememberProfile]);

  useEffect(() => {
    fetch('/api/health')
      .then(async (response) => {
        if (!response.ok) throw new Error('Backend unavailable');
        const health = await response.json();
        setProviderStatus(health.provider_configured ? 'ready' : 'configuration_required');
        if (Number.isInteger(health.max_upload_mb) && health.max_upload_mb > 0) setMaxUploadMB(health.max_upload_mb);
      })
      .catch(() => setProviderStatus('offline'));
  }, []);

  function acceptFile(next: File | undefined) {
    if (!next) return;
    const problem = validateImage(next, maxUploadMB * 1024 * 1024);
    setError(problem ?? '');
    if (problem) return;
    setFile(next);
    setResult(null);
    setNotice('');
  }

  function openFilePicker() {
    if (!inputRef.current) return;
    inputRef.current.value = '';
    inputRef.current.click();
  }

  function openCorrections() {
    if (!result) return;
    setEditedIngredients(result.label.ingredients.map((item) => item.source_text).join('\n'));
    setEditedIngredientsStatus(result.label.ingredients_status);
    setEditedNutrition(result.label.nutrition.map((item) => `${item.nutrient} | ${item.value ?? ''} | ${item.unit ?? ''} | ${item.basis ?? ''} | ${item.source_text ?? ''}`).join('\n'));
    setEditedAllergen(result.label.allergen_statement.source_text ?? '');
    setEditedAllergenStatus(result.label.allergen_statement.status);
    setEditedText(result.label.full_text);
    setCorrectionError('');
    setEditingExtraction(true);
  }

  async function runAnalysis() {
    if (!file) { setError('Choose a label photo to begin.'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await analyzeImage(file, profile);
      setResult(response);
      setEditedIngredients(response.label.ingredients.map((item) => item.source_text).join('\n'));
      setEditedIngredientsStatus(response.label.ingredients_status);
      setEditedNutrition(response.label.nutrition.map((item) => `${item.nutrient} | ${item.value ?? ''} | ${item.unit ?? ''} | ${item.basis ?? ''} | ${item.source_text ?? ''}`).join('\n'));
      setEditedAllergen(response.label.allergen_statement.source_text ?? '');
      setEditedAllergenStatus(response.label.allergen_statement.status);
      setEditedText(response.label.full_text);
      window.requestAnimationFrame?.(() => resultsRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please retry.');
    } finally { setBusy(false); }
  }

  async function rerunComparison(label = result?.label) {
    if (!label) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await compareLabel(label, profile);
      setResult(response);
      setNotice('Comparison updated using the reviewed label text.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update the comparison.'); }
    finally { setBusy(false); }
  }

  function saveCorrections() {
    if (!result) return;
    const lines = editedIngredients.split('\n').map((line) => line.trim()).filter(Boolean);
    const extractionWarnings = result.label.extraction_warnings.filter((warning) => {
      if (editedText.trim() && warning.startsWith('No full-label transcription was returned;')) return false;
      if (lines.length && warning.startsWith('An extracted ingredient has no exact source wording')) return false;
      return true;
    });
    const nutrition: LabelData['nutrition'] = [];
    for (const [index, row] of editedNutrition.split('\n').map((line) => line.trim()).filter(Boolean).entries()) {
      const [nutrient, rawValue, unit, basis, ...sourceParts] = row.split('|').map((part) => part.trim());
      if (!nutrient || rawValue === undefined || unit === undefined || basis === undefined || sourceParts.length === 0) {
        setCorrectionError(`Nutrition row ${index + 1} needs nutrient | value | unit | basis | exact source text.`);
        return;
      }
      const numericValue = rawValue === '' ? null : Number(rawValue);
      if (numericValue !== null && !Number.isFinite(numericValue)) {
        setCorrectionError(`Nutrition row ${index + 1} has an invalid numeric value.`);
        return;
      }
      nutrition.push({ nutrient, value: numericValue, unit: unit || null, basis: basis || null, source_text: sourceParts.join(' | ') || null, status: numericValue === null ? 'partially_readable' : 'visible' });
    }
    setCorrectionError('');
    const updated = {
      ...result.label,
      ingredients: lines.map((line) => ({
        name: line, source_text: line, normalized_name: line.toLowerCase(),
        status: editedIngredientsStatus === 'visible' ? 'visible' as const : editedIngredientsStatus,
      })),
      ingredients_status: lines.length ? editedIngredientsStatus : 'partially_readable' as const,
      nutrition,
      allergen_statement: {
        value: editedAllergen.trim() || null,
        source_text: editedAllergen.trim() || null,
        status: editedAllergen.trim() && editedAllergenStatus === 'visible'
          ? 'visible' as const
          : editedAllergenStatus === 'visible' ? 'unknown' as const : editedAllergenStatus,
        confidence: editedAllergen.trim() && editedAllergenStatus === 'visible' ? 1 : null,
      },
      extraction_warnings: extractionWarnings,
      full_text: editedText,
    };
    setEditingExtraction(false);
    void rerunComparison(updated);
  }

  function setThreshold(nutrient: string, direction: string, unit: string, value: string) {
    setProfile((current) => ({
      ...current,
      nutrition_thresholds: current.nutrition_thresholds.filter((item) => item.nutrient !== nutrient)
        .concat(value === '' ? [] : [{ nutrient, direction, unit, basis: 'per serving', value: Number(value) }]),
    }));
  }

  function addCustomAvoid(value: string) {
    if (value && !profile.avoid_ingredients.includes(value)) setProfile({ ...profile, avoid_ingredients: [...profile.avoid_ingredients, value] });
  }

  function addCustomPattern(value: string) {
    if (value && !profile.dietary_patterns.includes(value)) setProfile({ ...profile, dietary_patterns: [...profile.dietary_patterns, value] });
  }

  function addCustomNutrient() {
    const nutrient = customNutrient.trim();
    if (!nutrient || customNutrientValue === '') return;
    setProfile((current) => ({
      ...current,
      nutrition_thresholds: current.nutrition_thresholds.filter((item) => item.nutrient.toLowerCase() !== nutrient.toLowerCase())
        .concat([{ nutrient, direction: customNutrientDirection, unit: customNutrientUnit, basis: 'per serving', value: Number(customNutrientValue) }]),
    }));
    setCustomNutrient(''); setCustomNutrientValue('');
  }

  const findings = result?.findings ?? [];
  const filteredFindings = findings.filter((finding) => {
    if (filter === 'all') return true;
    if (filter === 'conflicts') return finding.status === 'conflict_detected';
    if (filter === 'potential') return finding.status === 'potential_conflict';
    if (filter === 'unknown') return ['unknown', 'insufficient_information'].includes(finding.status);
    return finding.status === 'no_conflict_found';
  });
  const hasRisk = findings.some((finding) => ['conflict_detected', 'potential_conflict'].includes(finding.status));
  const hasUnknown = findings.some((finding) => ['unknown', 'insufficient_information'].includes(finding.status));
  const reviewReasons = result ? [
    result.label.image_quality === 'limited' || result.label.image_quality === 'unreadable'
      ? `Image quality: ${result.label.image_quality.replace(/_/g, ' ')}.` : '',
    result.label.image_issues.length
      ? `Possible image issues: ${result.label.image_issues.map((issue) => issue.replace(/_/g, ' ')).join(', ')}.` : '',
    result.label.ingredients_status !== 'visible'
      ? `Ingredient list: ${result.label.ingredients_status.replace(/_/g, ' ')}.` : '',
    result.label.ingredients.some((item) => !item.source_text.trim() || item.status !== 'visible' || (item.confidence != null && item.confidence < 0.8))
      ? 'One or more ingredient readings have incomplete source text or low confidence.' : '',
    result.label.allergen_statement.status !== 'visible'
      ? `Allergen statement: ${result.label.allergen_statement.status.replace(/_/g, ' ')}.` : '',
    result.label.allergen_statement.confidence != null && result.label.allergen_statement.confidence < 0.8
      ? 'The allergen statement has low extraction confidence.' : '',
    result.label.nutrition.some((item) => item.status !== 'visible' || !item.source_text?.trim())
      ? 'One or more nutrition values lack complete readable source wording.' : '',
    ['partially_readable', 'unreadable'].includes(result.label.product_name.status) ||
      (result.label.product_name.value && (!result.label.product_name.source_text?.trim() || result.label.product_name.status !== 'visible'))
      ? 'The product name needs source-text confirmation.' : '',
    ['partially_readable', 'unreadable'].includes(result.label.serving_size.status) ||
      (result.label.serving_size.value && (!result.label.serving_size.source_text?.trim() || result.label.serving_size.status !== 'visible'))
      ? 'The serving size needs source-text confirmation.' : '',
    [...result.label.dietary_claims, ...result.label.certifications].some((item) =>
      ['partially_readable', 'unreadable'].includes(item.status) || (item.status === 'visible' && !item.source_text?.trim()))
      ? 'One or more claims or certifications need source-text confirmation.' : '',
    ...result.label.unreadable_regions,
    ...result.warnings,
  ].filter(Boolean) : [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <a href="#analyze" className="brand" aria-label="LabelLens AI home"><span className="brand-mark"><Leaf size={19} strokeWidth={2.2} /></span><span>label<span className="brand-light">lens</span><small>AI</small></span></a>
        <nav className="main-nav" aria-label="Main navigation">
          <a className="nav-active" href="#analyze">Analyze</a><a href="#profile">Dietary profile</a><a href="#how-it-works">How it works</a>
        </nav>
        <button className="disclaimer-link" onClick={() => setShowDisclaimer(true)}><ShieldCheck size={16} /> Safety & privacy</button>
      </header>

      <main>
        <section className="intro" id="analyze">
          <div className="intro-copy"><div className="eyebrow"><span className="eyebrow-line" /> LABEL READING, WITH CONTEXT</div>
            <h1>Know what’s<br /><em>in the fine print.</em></h1>
            <p>Read a food label against the things that matter to you. Every result comes with the wording it came from.</p>
          </div>
          <aside className="intro-showcase" aria-label="Illustration of how a label review works">
            <div className="showcase-heading"><span className="showcase-icon"><FileImage size={17} /></span><span><small>THE IDEA</small><strong>From label to clarity</strong></span><Sparkles size={16} /></div>
            <div className="label-preview-card">
              <div className="label-preview-heading"><strong>INGREDIENTS</strong><span>EXAMPLE</span></div>
              <p>Rolled oats, almonds, cane sugar, sea salt.</p>
              <div className="evidence-preview"><span className="evidence-preview-mark"><Check size={13} /></span><span><strong>Evidence, not guesswork</strong><small>Findings link back to visible wording.</small></span><ArrowRight size={15} /></div>
            </div>
            <div className="showcase-footnote"><ShieldCheck size={14} /><span>Evidence first. No safety guarantees.</span></div>
          </aside>
        </section>

        {providerStatus === 'configuration_required' && <div className="config-banner" role="status"><AlertTriangle size={17} /><span><b>Live analysis needs backend setup.</b> Configure the vision API key and model in the backend environment; profile comparison remains local to the service.</span></div>}
        {providerStatus === 'offline' && <div className="config-banner" role="status"><AlertCircle size={17} /><span><b>Analysis service is unavailable.</b> Start the backend and retry your image analysis.</span></div>}

        <div className="workspace-grid">
          <section className="upload-panel panel" aria-labelledby="upload-heading">
            <div className="panel-heading"><div><span className="section-kicker">01 / LABEL PHOTO</span><h2 id="upload-heading">Start with the package</h2></div><span className="step-number">01</span></div>
            {!file ? <div className={`dropzone ${dragging ? 'is-dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]); }}>
              <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => acceptFile(event.target.files?.[0])} />
              <div className="upload-icon"><Upload size={21} /></div><h3>Drop a label photo here</h3><p>Ingredient list, nutrition panel, or allergen statement</p>
              <button className="button button-outline" onClick={openFilePicker}><FileImage size={16} /> Choose image</button>
              <span className="file-note">JPEG, PNG or WebP · up to {maxUploadMB} MB</span>
            </div> : <div className="preview-wrap"><img src={preview} alt="Selected food package label preview" /><div className="preview-actions"><span><Check size={14} /> Image ready</span><button aria-label="Remove image" title="Remove image" onClick={() => { setFile(null); setResult(null); }}><X size={16} /></button></div><button className="replace-button" onClick={openFilePicker}>Replace photo</button><input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => acceptFile(event.target.files?.[0])} /></div>}
            <div className="privacy-inline"><ShieldCheck size={15} /><span>Photos are sent to your configured AI provider for analysis and are not stored by this app.</span></div>
            <button className="button button-primary analyze-button" onClick={() => void runAnalysis()} disabled={!file || busy}>{busy ? <><LoaderCircle className="spin" size={17} /> Analyzing label…</> : <><Sparkles size={16} /> Analyze this label <ArrowRight size={16} /></>}</button>
            {busy && <p className="busy-note" role="status">Waiting for the vision provider to read the visible label text.</p>}
            {error && <div className="error-box" role="alert"><AlertCircle size={17} /><span>{error}</span>{file && !busy && <button onClick={() => void runAnalysis()}>Retry</button>}</div>}
          </section>

          <section className="profile-panel panel" id="profile" aria-labelledby="profile-heading">
            <div className="panel-heading"><div><span className="section-kicker">02 / YOUR PREFERENCES</span><h2 id="profile-heading">What should we look for?</h2></div><span className="step-number">02</span></div>
            <p className="panel-intro">Choose any that apply. Dietary patterns are assessed cautiously and are not medical allergy rules.</p>
            <div className="preference-group"><h3>Allergens & ingredients</h3><div className="chip-grid">{allergenOptions.map((item) => <label className="check-chip" key={item}><input type="checkbox" checked={profile.allergens.includes(item.toLowerCase())} onChange={() => setProfile({ ...profile, allergens: toggle(profile.allergens, item.toLowerCase()) })} /><span>{item}</span></label>)}</div>
              <form className="custom-entry" onSubmit={avoidForm.handleSubmit(({ value }) => { addCustomAvoid(value); avoidForm.reset(); })}><input {...avoidForm.register('value')} placeholder="Add an ingredient or allergen" aria-label="Custom ingredient or allergen" /><button type="submit" aria-label="Add ingredient restriction">Add</button></form>
              {avoidForm.formState.errors.value && <p className="form-error">{avoidForm.formState.errors.value.message}</p>}
              {profile.avoid_ingredients.map((item) => <button className="removable-tag" key={item} onClick={() => setProfile({ ...profile, avoid_ingredients: profile.avoid_ingredients.filter((entry) => entry !== item) })}>{item}<X size={13} /></button>)}
            </div>
            <div className="preference-group"><h3>Dietary patterns</h3><div className="chip-grid pattern-grid">{patternOptions.map((item) => <label className="check-chip" key={item}><input type="checkbox" checked={profile.dietary_patterns.includes(item.toLowerCase())} onChange={() => setProfile({ ...profile, dietary_patterns: toggle(profile.dietary_patterns, item.toLowerCase()) })} /><span>{item}</span></label>)}</div>
              <form className="custom-entry" onSubmit={patternForm.handleSubmit(({ value }) => { addCustomPattern(value); patternForm.reset(); })}><input {...patternForm.register('value')} placeholder="Add a dietary requirement" aria-label="Custom dietary requirement" /><button type="submit" aria-label="Add dietary pattern">Add</button></form>
              {patternForm.formState.errors.value && <p className="form-error">{patternForm.formState.errors.value.message}</p>}
              {profile.dietary_patterns.filter((item) => !patternOptions.some((option) => option.toLowerCase() === item)).map((item) => <button className="removable-tag" key={item} onClick={() => setProfile({ ...profile, dietary_patterns: profile.dietary_patterns.filter((entry) => entry !== item) })}>{item}<X size={13} /></button>)}
            </div>
            <div className="preference-group"><h3>Ingredient preferences</h3><label className="switch-row"><input type="checkbox" checked={profile.avoid_palm_oil} onChange={(event) => setProfile({ ...profile, avoid_palm_oil: event.target.checked })} /><span>Avoid palm oil</span></label><label className="switch-row"><input type="checkbox" checked={profile.avoid_artificial_sweeteners} onChange={(event) => setProfile({ ...profile, avoid_artificial_sweeteners: event.target.checked })} /><span>Avoid artificial sweeteners</span></label></div>
            <div className="preference-group nutrition-group"><h3>Nutrition per serving <span>optional thresholds</span></h3><div className="threshold-grid">{nutrients.map((item) => <label className="threshold-input" key={item.nutrient}><span>{item.direction === 'maximum' ? 'Max' : 'Min'} {item.nutrient.toLowerCase()}</span><div><input type="number" min="0" step="any" aria-label={`${item.direction} ${item.nutrient}`} placeholder="—" value={profile.nutrition_thresholds.find((entry) => entry.nutrient === item.nutrient)?.value ?? ''} onChange={(event) => setThreshold(item.nutrient, item.direction, item.unit, event.target.value)} /><small>{item.unit}</small></div></label>)}</div>
              <div className="custom-threshold"><input aria-label="Custom nutrient name" value={customNutrient} onChange={(event) => setCustomNutrient(event.target.value)} placeholder="Nutrient" /><select aria-label="Custom threshold direction" value={customNutrientDirection} onChange={(event) => setCustomNutrientDirection(event.target.value)}><option value="maximum">Max</option><option value="minimum">Min</option></select><input aria-label="Custom nutrient threshold" type="number" min="0" step="any" value={customNutrientValue} onChange={(event) => setCustomNutrientValue(event.target.value)} placeholder="Value" /><select aria-label="Custom nutrient unit" value={customNutrientUnit} onChange={(event) => setCustomNutrientUnit(event.target.value)}><option>g</option><option>mg</option><option>kcal</option></select><button aria-label="Add custom nutrient threshold" onClick={addCustomNutrient}>Add</button></div>
              {profile.nutrition_thresholds.filter((item) => !nutrients.some((known) => known.nutrient === item.nutrient)).map((item) => <button className="removable-tag" key={item.nutrient} onClick={() => setProfile({ ...profile, nutrition_thresholds: profile.nutrition_thresholds.filter((entry) => entry.nutrient !== item.nutrient) })}>{item.direction === 'maximum' ? 'Max' : 'Min'} {item.nutrient} {item.value} {item.unit}<X size={13} /></button>)}
            </div>
            <label className="remember-row"><input type="checkbox" checked={rememberProfile} onChange={(event) => setRememberProfile(event.target.checked)} /><span>Remember my preferences on this device</span><span title="Stored only in this browser. You can clear it by unchecking this option."><CircleHelp size={14} aria-hidden="true" /></span></label>
            {result && <button className="button button-outline rerun-button" disabled={busy} onClick={() => void rerunComparison()}><RotateCcw size={15} /> Rerun comparison with this profile</button>}
          </section>
        </div>

        {result && <section className="results-section" ref={resultsRef} aria-labelledby="results-heading">
          <div className="results-topline"><div><span className="section-kicker">03 / LABEL REVIEW</span><h2 id="results-heading">What we found</h2></div><button className="text-button" onClick={() => { setFile(null); setResult(null); setError(''); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Analyze another <ArrowRight size={15} /></button></div>
          {reviewReasons.length > 0 && <div className="warning-banner label-review-banner" role="status"><AlertTriangle size={18} /><div><strong>Some label information needs confirmation.</strong><p>{reviewReasons.join(' ')} A missing word in the extracted text does not prove that an ingredient or allergen is absent. Retake the photo or check the original package before relying on this reading.</p><div className="review-actions"><button className="button button-outline" onClick={openFilePicker}><FileImage size={15} /> Choose a clearer photo</button><button className="button button-primary" onClick={openCorrections}><Check size={15} /> Review and confirm fields</button></div></div></div>}
          <div className={`assessment-banner ${hasRisk ? 'assessment-risk' : hasUnknown ? 'assessment-uncertain' : 'assessment-neutral'}`}><span className="assessment-mark">{hasRisk ? <AlertTriangle size={20} /> : hasUnknown ? <CircleHelp size={20} /> : <ShieldCheck size={20} />}</span><div><span className="section-kicker">IMAGE-BASED REVIEW ONLY</span><h3>{hasRisk ? 'Potential conflicts need your attention' : hasUnknown ? 'Some preferences could not be assessed' : findings.length ? 'No selected matches detected in reviewed text' : 'No preferences selected'}</h3><p>This review covers only the text visible in the supplied image. It cannot confirm manufacturing cross-contact, ingredient sourcing, or certification.</p></div></div>
          <div className="result-layout">
            <div className="findings-column"><div className="section-title-row"><h3>Preference findings <span>{findings.length}</span></h3><label className="filter-control"><span className="sr-only">Filter findings</span><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All findings</option><option value="conflicts">Conflicts</option><option value="potential">Potential conflicts</option><option value="unknown">Unknown / insufficient</option><option value="clear">No match found</option></select><ChevronDown size={14} /></label></div>
              {filteredFindings.length ? <div className="finding-list">{filteredFindings.map((finding, index) => <FindingCard finding={finding} key={`${finding.preference}-${index}`} onEvidence={() => document.getElementById('source-text')?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })} />)}</div> : <div className="empty-findings"><CircleHelp size={18} /><span>No findings in this filter.</span></div>}
            </div>
            <aside className="label-data-column"><div className="data-block"><div className="data-heading"><h3>Product name</h3><span className={`data-state state-${result.label.product_name.status}`}>{result.label.product_name.status.replace(/_/g, ' ')}</span></div><p className="quote-text">{result.label.product_name.source_text || 'No exact product-name wording extracted.'}</p></div>
              <div className="data-block"><div className="data-heading"><h3>Ingredient list</h3><span className={`data-state state-${result.label.ingredients_status}`}>{result.label.ingredients_status.replace(/_/g, ' ')}</span></div>{result.label.ingredients.length ? <ol className="ingredient-list">{result.label.ingredients.map((item, index) => <li key={`${index}-${item.source_text}`}><span>{item.source_text || 'No exact source wording extracted.'}</span><small className={`field-confidence ${!item.source_text.trim() || item.status !== 'visible' || (item.confidence != null && item.confidence < 0.8) ? 'confidence-uncertain' : ''}`}>{!item.source_text.trim() || item.status !== 'visible' ? item.status.replace(/_/g, ' ') : item.confidence != null ? `${Math.round(item.confidence * 100)}% confidence` : 'Readable text'}</small></li>)}</ol> : <p className="muted-copy">No ingredients were extracted from this image. This does not confirm that the label contains none.</p>}</div>
              <div className="data-block"><div className="data-heading"><h3>Nutrition facts</h3><span className="data-state">{result.label.nutrition.length} fields</span></div>{result.label.nutrition.length ? <div className="nutrition-table">{result.label.nutrition.map((item, index) => <div className="nutrition-row" key={`${item.nutrient}-${index}`}><span>{item.nutrient} <em className={`data-state state-${item.status}`}>{item.status.replace(/_/g, ' ')}</em></span><b>{item.status === 'visible' && item.source_text?.trim() && item.value != null ? `${item.value} ${item.unit ?? ''}` : 'Needs confirmation'}</b><small>{item.source_text || 'No exact source wording extracted.'}</small></div>)}</div> : <p className="muted-copy">No nutrition values extracted. This does not confirm that the label contains none.</p>}</div>
              <div className="data-block"><div className="data-heading"><h3>Allergen statement</h3><span className={`data-state state-${result.label.allergen_statement.status}`}>{result.label.allergen_statement.status.replace(/_/g, ' ')}</span></div><p className="quote-text">{result.label.allergen_statement.source_text || 'No readable allergen statement extracted. This does not mean the product is allergen-free.'}</p>{result.label.allergen_statement.confidence != null && <p className={`field-confidence ${result.label.allergen_statement.confidence < 0.8 ? 'confidence-uncertain' : ''}`}>{Math.round(result.label.allergen_statement.confidence * 100)}% extraction confidence; compare against the package.</p>}</div>
              <div className="data-block"><div className="data-heading"><h3>Serving size</h3><span className={`data-state state-${result.label.serving_size.status}`}>{result.label.serving_size.status.replace(/_/g, ' ')}</span></div><p className="quote-text">{result.label.serving_size.source_text || 'No exact serving-size wording extracted.'}</p></div>
              <div className="data-block"><div className="data-heading"><h3>Claims & certifications</h3></div>{[...result.label.dietary_claims, ...result.label.certifications].length ? [...result.label.dietary_claims, ...result.label.certifications].map((claim, index) => <div className="claim-row" key={index}><span className={`data-state state-${claim.status}`}>{claim.status.replace(/_/g, ' ')}</span><p className="quote-text">{claim.source_text || 'No exact source wording extracted; needs confirmation.'}</p></div>) : <p className="muted-copy">No claims or certification text extracted. This is not proof that none appear elsewhere on the package.</p>}</div>
            </aside>
          </div>
          <section className="source-panel" id="source-text"><div className="source-heading"><div><span className="section-kicker">VERIFY THE READING</span><h3>Extracted text & corrections</h3></div><button className="text-button" onClick={() => editingExtraction ? setEditingExtraction(false) : openCorrections()}>{editingExtraction ? 'Cancel edits' : 'Edit text'} <ChevronDown size={14} /></button></div>
            {editingExtraction ? <div className="correction-form"><label>Ingredients, one item per line<textarea value={editedIngredients} onChange={(event) => setEditedIngredients(event.target.value)} rows={5} /></label><label>Ingredient list status<select value={editedIngredientsStatus} onChange={(event) => setEditedIngredientsStatus(event.target.value as LabelData['ingredients_status'])}><option value="visible">Complete and readable</option><option value="partially_readable">Partially readable</option><option value="unreadable">Unreadable</option><option value="not_found_in_image">Not found in image</option><option value="unknown">Unknown</option></select></label><label>Nutrition rows: nutrient | value | unit | basis | source text<textarea value={editedNutrition} onChange={(event) => setEditedNutrition(event.target.value)} rows={5} /></label><label>Allergen statement, exact wording<textarea value={editedAllergen} onChange={(event) => setEditedAllergen(event.target.value)} rows={3} /></label><label>Allergen statement status<select value={editedAllergenStatus} onChange={(event) => setEditedAllergenStatus(event.target.value as LabelData['allergen_statement']['status'])}><option value="visible">Confirmed readable from package</option><option value="partially_readable">Partially readable</option><option value="unreadable">Unreadable</option><option value="not_found_in_image">Not found in image</option><option value="unknown">Needs confirmation</option></select></label><label>Full visible text<textarea value={editedText} onChange={(event) => setEditedText(event.target.value)} rows={5} /></label><p>Only mark a field complete after checking the original package. Keep unreadable wording unresolved; do not fill gaps by guessing. Nutrition values are compared only when unit and serving basis match.</p>{correctionError && <p className="form-error" role="alert">{correctionError}</p>}<button className="button button-primary" onClick={saveCorrections} disabled={busy}><Check size={15} /> Save corrections & compare</button></div> : <pre className="source-text">{result.label.full_text || 'No full text was returned. Review the structured values above and correct them against the image.'}</pre>}
            {notice && <p className="success-note" role="status"><Check size={14} /> {notice}</p>}
          </section>
          <p className="conclusion-note"><AlertCircle size={15} /> A missing ingredient in extracted text can mean it was absent from the visible list, missed by extraction, or outside the photographed area. Do not use this result alone to determine whether a product is safe.</p>
        </section>}

        <section className="how-section" id="how-it-works"><div className="how-title"><span className="section-kicker">A MORE CAREFUL READ</span><h2>How LabelLens works</h2></div><div className="how-steps"><article><span>01</span><h3>Read what’s visible</h3><p>A vision model extracts wording from the photo. Unclear sections stay marked as uncertain.</p></article><article><span>02</span><h3>Compare your profile</h3><p>Explicit ingredient and nutrition rules run locally in the backend against extracted label data.</p></article><article><span>03</span><h3>Check the evidence</h3><p>Each finding points back to the wording that triggered it. You can correct a reading and compare again.</p></article></div></section>
      </main>
      <footer className="footer"><a href="#analyze" className="brand footer-brand"><span className="brand-mark"><Leaf size={17} /></span><span>labellens<small>AI</small></span></a><span>Evidence-led label reading. Not medical advice.</span><button onClick={() => setShowDisclaimer(true)}>Privacy & limitations</button></footer>
      {showDisclaimer && <div className="modal-backdrop" role="presentation" onClick={() => setShowDisclaimer(false)}><section className="disclaimer-modal" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title" onClick={(event) => event.stopPropagation()}><button className="modal-close" aria-label="Close" onClick={() => setShowDisclaimer(false)}><X size={18} /></button><span className="modal-icon"><ShieldCheck size={20} /></span><span className="section-kicker">PLEASE READ</span><h2 id="disclaimer-title">Useful context, not a safety guarantee.</h2><p>LabelLens reviews only the image you provide. It can miss text, misread ingredients, and cannot verify manufacturing cross-contact, ingredient sourcing, or whether a certification is valid. No match detected is not proof that a product is allergen-free or compatible with your diet.</p><p>Images are sent to the AI provider configured by the operator for analysis. That provider may process data under its own terms. This app does not store images after the request. Saved preferences remain in this browser only when you opt in.</p><button className="button button-primary" onClick={() => setShowDisclaimer(false)}>Understood</button></section></div>}
    </div>
  );
}

function FindingCard({ finding, onEvidence }: { finding: Finding; onEvidence: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const tone = finding.status === 'conflict_detected' ? 'red' : finding.status === 'potential_conflict' ? 'amber' : finding.status === 'no_conflict_found' ? 'green' : 'gray';
  const Icon = finding.status === 'conflict_detected' ? AlertCircle : finding.status === 'potential_conflict' ? AlertTriangle : finding.status === 'no_conflict_found' ? Check : CircleHelp;
  return <article className={`finding-card finding-${tone}`}><div className="finding-main"><span className="finding-icon"><Icon size={17} /></span><div className="finding-content"><div className="finding-meta"><strong>{finding.preference}</strong><span className="status-label">{statusLabels[finding.status]}</span></div><p>{finding.summary}</p>{finding.evidence.map((evidence, index) => <button className="evidence-quote" key={index} onClick={onEvidence}><span>“{evidence.source_text}”</span><small>{evidence.field.replace(/_/g, ' ')}</small></button>)}{finding.uncertainty && <p className="uncertainty-copy"><CircleHelp size={13} /> {finding.uncertainty}</p>}<button className="reasoning-toggle" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Hide reasoning' : 'Why this result?'} <ChevronDown size={13} /></button>{expanded && <div className="reasoning-detail"><b>{finding.reasoning_type.replace(/_/g, ' ')}</b><p>{finding.evidence.map((evidence) => evidence.explanation).join(' ') || 'No direct label quotation supports a positive match. The result reflects incomplete or missing label information.'}</p></div>}</div></div></article>;
}

export default App;
