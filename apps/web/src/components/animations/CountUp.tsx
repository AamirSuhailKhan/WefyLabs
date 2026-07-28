'use client';

import { useRef } from 'react';
import { useInView } from 'framer-motion';
import CountUp from 'react-countup';

export function AnimatedCounter({
  end,
  prefix = '',
  suffix = '',
  duration = 2,
  className = '',
  decimals = 0,
}: {
  end: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
  decimals?: number;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <span ref={ref} className={className}>
      {isInView ? (
        <CountUp end={end} prefix={prefix} suffix={suffix} duration={duration} decimals={decimals} />
      ) : (
        <span>{prefix}0{suffix}</span>
      )}
    </span>
  );
}
