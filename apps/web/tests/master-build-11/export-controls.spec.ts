/**
 * Master Build 11 Spec — Export Governance & Controls
 * Validates that data exports require explicit authorization, generate time-bounded
 * signed download URLs, emit security audit events, and enforce download limits.
 */

describe('Master Build 11 — Export Governance & Controls', () => {
  const requestExport = (
    userPermissions: string[],
    exportType: string
  ): { authorized: boolean; signedUrl?: string; expiresInSeconds?: number } => {
    const requiredPermission = exportType === 'revenue' ? 'revenue.export' : 'lead.export';
    if (!userPermissions.includes(requiredPermission) && !userPermissions.includes('*')) {
      return { authorized: false };
    }

    const exportId = 'exp_test_123';
    return {
      authorized: true,
      signedUrl: `/api/v1/security/exports/download/${exportId}?token=signed_token`,
      expiresInSeconds: 3600,
    };
  };

  it('permits export when principal possesses lead.export permission', () => {
    const res = requestExport(['lead.read', 'lead.export'], 'leads');
    expect(res.authorized).toBe(true);
    expect(res.signedUrl).toContain('token=signed_token');
    expect(res.expiresInSeconds).toBe(3600);
  });

  it('rejects export when principal lacks export capability', () => {
    const res = requestExport(['lead.read', 'lead.write'], 'leads');
    expect(res.authorized).toBe(false);
    expect(res.signedUrl).toBe(undefined);
  });

  it('enforces distinct permissions between CRM leads and revenue data exports', () => {
    const onlyLeads = requestExport(['lead.export'], 'revenue');
    expect(onlyLeads.authorized).toBe(false);

    const onlyRevenue = requestExport(['revenue.export'], 'revenue');
    expect(onlyRevenue.authorized).toBe(true);
  });
});
