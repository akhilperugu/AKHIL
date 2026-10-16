import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

const label = {
  image_quality: 'clear' as const, image_issues: [],
  product_name: { value: 'Oat Bites', source_text: 'Oat Bites', status: 'visible' as const },
  ingredients: [{ name: 'milk', source_text: 'Milk powder', normalized_name: 'milk', status: 'visible' as const, confidence: 0.98 }],
  ingredients_status: 'visible' as const,
  allergen_statement: { value: 'Contains milk', source_text: 'Contains milk', status: 'visible' as const },
  nutrition: [], serving_size: { status: 'unknown' as const }, dietary_claims: [], certifications: [],
  other_visible_text: [], unreadable_regions: [], extraction_warnings: [], full_text: 'Ingredients: Milk powder',
};
const conflict = {
  preference: 'milk', status: 'conflict_detected' as const, severity: 'high' as const,
  summary: 'Milk appears in the visible ingredient list.',
  evidence: [{ source_text: 'Milk powder', field: 'ingredients', explanation: 'Direct ingredient match.' }],
  reasoning_type: 'direct_match', uncertainty: null,
};
const response = { label, findings: [conflict], warnings: [] };

beforeEach(() => {
  localStorage.clear();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:label') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready', provider_configured: true, max_upload_mb: 10 }) }));
});

describe('LabelLens workspace', () => {
  it('renders the upload flow and dietary profile controls', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: /know what’s in the fine print/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /choose image/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Milk')).toBeInTheDocument();
    expect(screen.getByLabelText('Avoid palm oil')).toBeInTheDocument();
  });

  it('shows evidence and supports corrected re-comparison', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => ({
      ok: true,
      json: async () => String(input).includes('/api/health') ? { status: 'ready', provider_configured: true, max_upload_mb: 10 } : response,
    } as Response));
    const { container } = render(<App />);
    fireEvent.click(screen.getByLabelText('Milk'));
    const fileInput = container.querySelector('input[type="file"]')!;
    fireEvent.change(fileInput, { target: { files: [new File(['label'], 'label.png', { type: 'image/png' })] } });
    fireEvent.click(screen.getByRole('button', { name: /analyze this label/i }));
    expect(await screen.findByRole('heading', { name: 'What we found' })).toBeInTheDocument();
    expect(screen.getByText('Conflict detected')).toBeInTheDocument();
    expect(screen.getByText('“Milk powder”')).toBeInTheDocument();
    expect(screen.getByText('Oat Bites')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /edit text/i }));
    fireEvent.change(screen.getByLabelText(/ingredients, one item per line/i), { target: { value: 'Cocoa' } });
    fireEvent.click(screen.getByRole('button', { name: /save corrections & compare/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/compare', expect.anything()));
    expect(await screen.findByText('Comparison updated using the reviewed label text.')).toBeInTheDocument();
  });

  it('renders a readable provider error', async () => {
    vi.mocked(fetch).mockImplementation(async (input) => String(input).includes('/api/health')
      ? { ok: true, json: async () => ({ status: 'ready', provider_configured: true, max_upload_mb: 10 }) } as Response
      : { ok: false, json: async () => ({ detail: 'Vision provider is not configured.' }) } as Response);
    const { container } = render(<App />);
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(['label'], 'label.png', { type: 'image/png' })] } });
    fireEvent.click(screen.getByRole('button', { name: /analyze this label/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Vision provider is not configured.');
  });

  it('asks for confirmation on an unclear label and re-compares user corrections', async () => {
    const unclearResponse = {
      ...response,
      label: {
        ...label,
        image_quality: 'limited' as const,
        image_issues: ['curved_surface'] as const,
        ingredients_status: 'partially_readable' as const,
        ingredients: [{ name: 'milk', source_text: 'Milk powd…', status: 'partially_readable' as const, confidence: 0.54 }],
        allergen_statement: { value: null, source_text: 'Contains mil…', status: 'partially_readable' as const, confidence: 0.5 },
      },
      findings: [{
        ...conflict,
        status: 'insufficient_information' as const,
        summary: 'Image quality prevents confirming that the full ingredient list was read.',
        evidence: [{ source_text: 'Milk powd…', field: 'ingredients', explanation: 'This wording is only partially readable.' }],
        uncertainty: 'Retake the photo or manually confirm the complete ingredient list against the package.',
      }],
    };
    let comparedLabel: typeof unclearResponse.label | undefined;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (String(input).includes('/api/health')) {
        return { ok: true, json: async () => ({ status: 'ready', provider_configured: true, max_upload_mb: 10 }) } as Response;
      }
      if (String(input).includes('/api/compare')) {
        comparedLabel = JSON.parse(String(init?.body)).label;
        return { ok: true, json: async () => ({ ...response, label: comparedLabel }) } as Response;
      }
      return { ok: true, json: async () => unclearResponse } as Response;
    });

    const { container } = render(<App />);
    fireEvent.click(screen.getByLabelText('Milk'));
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(['label'], 'label.png', { type: 'image/png' })] } });
    fireEvent.click(screen.getByRole('button', { name: /analyze this label/i }));

    expect(await screen.findByText(/some label information needs confirmation/i)).toBeInTheDocument();
    expect(screen.getByText(/curved surface/i)).toBeInTheDocument();
    expect(screen.getByText(/does not prove that an ingredient or allergen is absent/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /review and confirm fields/i }));

    fireEvent.change(screen.getByLabelText(/ingredients, one item per line/i), { target: { value: 'Milk powder\nCocoa' } });
    fireEvent.change(screen.getByLabelText('Ingredient list status'), { target: { value: 'visible' } });
    fireEvent.change(screen.getByLabelText('Allergen statement, exact wording'), { target: { value: 'Contains milk' } });
    fireEvent.change(screen.getByLabelText('Allergen statement status'), { target: { value: 'visible' } });
    fireEvent.click(screen.getByRole('button', { name: /save corrections & compare/i }));

    await waitFor(() => expect(comparedLabel?.ingredients[0]?.source_text).toBe('Milk powder'));
    expect(comparedLabel?.ingredients_status).toBe('visible');
    expect(comparedLabel?.allergen_statement.source_text).toBe('Contains milk');
    expect(comparedLabel?.allergen_statement.status).toBe('visible');
    expect(await screen.findByText('Comparison updated using the reviewed label text.')).toBeInTheDocument();
  });

  it('does not present unsupported structured values as verified label evidence', async () => {
    const unverifiedResponse = {
      ...response,
      label: {
        ...label,
        product_name: { value: 'Invented Product', source_text: null, status: 'unknown' as const },
        nutrition: [{
          nutrient: 'Sugar', value: 99, unit: 'g', basis: 'per serving',
          source_text: 'Sugar 4 g per serving', status: 'partially_readable' as const,
        }],
        serving_size: { value: '30 g', source_text: null, status: 'unknown' as const },
        dietary_claims: [{ value: 'Vegan', source_text: null, status: 'unknown' as const }],
      },
      findings: [],
    };
    vi.mocked(fetch).mockImplementation(async (input) => String(input).includes('/api/health')
      ? { ok: true, json: async () => ({ status: 'ready', provider_configured: true, max_upload_mb: 10 }) } as Response
      : { ok: true, json: async () => unverifiedResponse } as Response);

    const { container } = render(<App />);
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(['label'], 'label.png', { type: 'image/png' })] } });
    fireEvent.click(screen.getByRole('button', { name: /analyze this label/i }));

    expect(await screen.findByRole('heading', { name: 'What we found' })).toBeInTheDocument();
    expect(screen.queryByText('Invented Product')).not.toBeInTheDocument();
    expect(screen.queryByText('99 g')).not.toBeInTheDocument();
    expect(screen.queryByText('30 g')).not.toBeInTheDocument();
    expect(screen.getByText(/No exact source wording extracted; needs confirmation/)).toBeInTheDocument();
    expect(screen.getByText('Sugar 4 g per serving')).toBeInTheDocument();
    expect(screen.getByText('Needs confirmation')).toBeInTheDocument();
  });
});
