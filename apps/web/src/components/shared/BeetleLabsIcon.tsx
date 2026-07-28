import React from 'react';

interface BeetleLabsIconProps {
  className?: string;
  size?: number | string;
  fill?: string;
}

export function BeetleLabsIcon({ className = '', size = 28, fill = 'currentColor' }: BeetleLabsIconProps) {
  // Precision dot-matrix halftone 'B' logo generator matching the reference brand asset
  const spacingX = 6;
  const spacingY = 6;
  const offsetX = 8;
  const offsetY = 6;

  // Grid dimensions: 13 columns (0..12), 15 rows (0..14)
  const dots: Array<{ x: number; y: number; r: number; opacity: number }> = [];

  // Radius map by column (Halftone progression fading to left)
  const getRadius = (col: number): number => {
    if (col >= 10) return 2.6;
    if (col === 9) return 2.5;
    if (col === 8) return 2.3;
    if (col === 7) return 2.0;
    if (col === 6) return 1.7;
    if (col === 5) return 1.4;
    if (col === 4) return 1.1;
    if (col === 3) return 0.85;
    if (col === 2) return 0.65;
    if (col === 1) return 0.5;
    return 0.38; // col 0
  };

  // Opacity map by column
  const getOpacity = (col: number): number => {
    if (col >= 6) return 1.0;
    if (col === 5) return 0.95;
    if (col === 4) return 0.88;
    if (col === 3) return 0.78;
    if (col === 2) return 0.65;
    if (col === 1) return 0.50;
    return 0.35;
  };

  // Helper to determine if a grid coordinate (row, col) is part of the letter 'B'
  const isDotInB = (row: number, col: number): boolean => {
    // Upper hole (rows 3, 4; cols 7, 8)
    if ((row === 3 || row === 4) && (col === 7 || col === 8)) {
      return false;
    }

    // Lower hole (rows 10, 11; cols 7, 8)
    if ((row === 10 || row === 11) && (col === 7 || col === 8)) {
      return false;
    }

    // Outer right boundary contours for upper and lower bowls
    // Row 0 (top cap): cols 3..10
    if (row === 0) return col >= 3 && col <= 10;
    // Row 1 & 2 (top bar/upper bowl top): cols 2..11
    if (row === 1 || row === 2) return col >= 2 && col <= 11;
    // Row 3 & 4 (upper bowl middle): cols 2..12
    if (row === 3 || row === 4) return col >= 2 && col <= 12;
    // Row 5 & 6 (upper bowl bottom / waist top): cols 2..11
    if (row === 5 || row === 6) return col >= 2 && col <= 11;
    // Row 7 (waist center indent): cols 1..10
    if (row === 7) return col >= 1 && col <= 10;
    // Row 8 & 9 (lower bowl top): cols 2..11
    if (row === 8 || row === 9) return col >= 2 && col <= 11;
    // Row 10 & 11 (lower bowl middle): cols 2..12
    if (row === 10 || row === 11) return col >= 2 && col <= 12;
    // Row 12 & 13 (lower bowl bottom): cols 2..11
    if (row === 12 || row === 13) return col >= 2 && col <= 11;
    // Row 14 (bottom cap): cols 3..10
    if (row === 14) return col >= 3 && col <= 10;

    // Dissolve trail particles on far left for key accent rows (0, 7, 14)
    if ((row === 0 || row === 7 || row === 14) && (col === 0 || col === 1 || col === 2)) {
      return true;
    }

    return false;
  };

  // Generate grid dots
  for (let r = 0; r <= 14; r++) {
    for (let c = 0; c <= 12; c++) {
      if (isDotInB(r, c)) {
        dots.push({
          x: offsetX + c * spacingX,
          y: offsetY + r * spacingY,
          r: getRadius(c),
          opacity: getOpacity(c),
        });
      }
    }
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 92 98"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {dots.map((dot, idx) => (
        <circle
          key={idx}
          cx={dot.x}
          cy={dot.y}
          r={dot.r}
          fill={fill}
          fillOpacity={dot.opacity}
        />
      ))}
    </svg>
  );
}
