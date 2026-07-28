'use client';

import CountUp from 'react-countup';
import { useInView } from 'framer-motion';
import { useRef } from 'react';

export function CountUpNumber({
  end,
  prefix = '',
  suffix = '',
  duration = 2.5,
  decimals = 0,
}: {
  end: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  decimals?: number;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  return (
    <span ref={ref}>
      {isInView ? (
        <CountUp end={end} prefix={prefix} suffix={suffix} duration={duration} decimals={decimals} />
      ) : (
        `${prefix}0${suffix}`
      )}
    </span>
  );
}
