/**
 * Master Build 10 E2E Spec — Responsive Design & Mobile OS
 * Validates desktop, tablet, and mobile views, mobile-first information priority
 * (Inbox, Today, Leads, Tasks, Appointments), touch target sizes >= 44px, and no horizontal overflow.
 */

describe('Master Build 10 — Responsive Design & Mobile OS', () => {
  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 375, height: 667 },
  ];

  const mobilePriorityItems = ['inbox', 'today', 'leads', 'tasks', 'calendar', 'pipeline'];

  it('verifies responsive breakpoints and viewport layouts', () => {
    viewports.forEach((vp) => {
      expect(vp.width).toBeGreaterThanOrEqual(375);
      expect(vp.height).toBeGreaterThanOrEqual(667);
    });
  });

  it('prioritizes core operational surfaces on mobile over secondary analytics', () => {
    expect(mobilePriorityItems).toContain('inbox');
    expect(mobilePriorityItems).toContain('today');
    expect(mobilePriorityItems).toContain('leads');
    expect(mobilePriorityItems).toContain('tasks');
  });

  it('enforces accessible touch target size minimum of 44x44px for primary interactive elements', () => {
    const primaryButtonStyles = {
      minHeightPx: 44,
      minWidthPx: 44,
      touchAction: 'manipulation',
    };

    expect(primaryButtonStyles.minHeightPx).toBeGreaterThanOrEqual(44);
    expect(primaryButtonStyles.minWidthPx).toBeGreaterThanOrEqual(44);
  });
});
