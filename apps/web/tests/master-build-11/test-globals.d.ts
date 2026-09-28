// Type definitions for Master Build 11 E2E Specs

declare function describe(name: string, fn: () => void): void;
declare function it(name: string, fn: () => void | Promise<void>): void;
declare function expect(actual: any): {
  toBe(expected: any): void;
  toEqual(expected: any): void;
  toBeDefined(): void;
  toContain(expected: any): void;
  toMatch(expected: RegExp | string): void;
  not: {
    toBe(expected: any): void;
    toEqual(expected: any): void;
    toContain(expected: any): void;
  };
  toBeGreaterThan(expected: number): void;
  toBeGreaterThanOrEqual(expected: number): void;
  toBeLessThan(expected: number): void;
  toBeLessThanOrEqual(expected: number): void;
};
