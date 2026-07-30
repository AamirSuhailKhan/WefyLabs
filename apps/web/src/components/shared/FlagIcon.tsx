import React from 'react';
import { RegionCode } from '@/lib/i18n/regions';

interface FlagIconProps {
  code: RegionCode;
  className?: string;
}

export function FlagIcon({ code, className = "w-5 h-3.5 rounded-[2px] shadow-xs inline-block shrink-0 border border-black/10" }: FlagIconProps) {
  switch (code) {
    case 'IN':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="India Flag">
          <path fill="#FF9933" d="M0 0h640v160H0z"/>
          <path fill="#FFFFFF" d="M0 160h640v160H0z"/>
          <path fill="#138808" d="M0 320h640v160H0z"/>
          <circle cx="320" cy="240" r="60" fill="none" stroke="#000080" strokeWidth="8"/>
          <circle cx="320" cy="240" r="10" fill="#000080"/>
          <path fill="none" stroke="#000080" strokeWidth="4" d="M320 180v120M260 240h120M277.6 197.6l84.8 84.8M277.6 282.4l84.8-84.8M290 188l60 104M290 292l60-104M349.9 188l-60 104M349.9 292l-60-104"/>
        </svg>
      );
    case 'AE':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="UAE Flag">
          <path fill="#009739" d="M160 0h480v160H160z"/>
          <path fill="#FFFFFF" d="M160 160h480v160H160z"/>
          <path fill="#000000" d="M160 320h480v160H160z"/>
          <path fill="#EF3340" d="M0 0h160v480H0z"/>
        </svg>
      );
    case 'SG':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="Singapore Flag">
          <path fill="#ED2939" d="M0 0h640v240H0z"/>
          <path fill="#FFFFFF" d="M0 240h640v240H0z"/>
          <path fill="#FFFFFF" d="M140 120a65 65 0 1 0 0-130 80 80 0 1 1 0 130z" transform="translate(10 10)"/>
          <g fill="#FFFFFF" transform="translate(180 55) scale(1.1)">
            <polygon points="12,0 15,9 24,9 17,14 19,23 12,18 5,23 7,14 0,9 9,9"/>
            <polygon points="35,-10 38,-1 47,-1 40,4 42,13 35,8 28,13 30,4 23,-1 32,-1"/>
            <polygon points="35,10 38,19 47,19 40,24 42,33 35,28 28,33 30,24 23,19 32,19"/>
            <polygon points="50,-3 53,6 62,6 55,11 57,20 50,15 43,20 45,11 38,6 47,6"/>
            <polygon points="50,13 53,22 62,22 55,27 57,36 50,31 43,36 45,27 38,22 47,22"/>
          </g>
        </svg>
      );
    case 'GB':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="UK Flag">
          <path fill="#012169" d="M0 0h640v480H0z"/>
          <path stroke="#FFF" strokeWidth="60" d="M0 0l640 480M640 0L0 480"/>
          <path stroke="#C8102E" strokeWidth="40" d="M0 0l640 480M640 0L0 480"/>
          <path stroke="#FFF" strokeWidth="100" d="M320 0v480M0 240h640"/>
          <path stroke="#C8102E" strokeWidth="60" d="M320 0v480M0 240h640"/>
        </svg>
      );
    case 'US':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="USA Flag">
          <path fill="#B22234" d="M0 0h640v480H0z"/>
          <path fill="#FFFFFF" d="M0 36.9h640v36.9H0zm0 73.8h640v36.9H0zm0 73.9h640v36.9H0zm0 73.8h640v36.9H0zm0 73.9h640v36.9H0zm0 73.8h640v36.9H0z"/>
          <path fill="#3C3B6E" d="M0 0h280v258.5H0z"/>
          <g fill="#FFFFFF">
            <polygon points="24,12 26,19 33,19 27,23 29,30 24,25 19,30 21,23 15,19 22,19"/>
            <polygon points="80,12 82,19 89,19 83,23 85,30 80,25 75,30 77,23 71,19 78,19"/>
            <polygon points="136,12 138,19 145,19 139,23 141,30 136,25 131,30 133,23 127,19 134,19"/>
            <polygon points="192,12 194,19 201,19 195,23 197,30 192,25 187,30 189,23 183,19 190,19"/>
            <polygon points="248,12 250,19 257,19 251,23 253,30 248,25 243,30 245,23 239,19 246,19"/>
            <polygon points="52,40 54,47 61,47 55,51 57,58 52,53 47,58 49,51 43,47 50,47"/>
            <polygon points="108,40 110,47 117,47 111,51 113,58 108,53 103,58 105,51 99,47 106,47"/>
            <polygon points="164,40 166,47 173,47 167,51 169,58 164,53 159,58 161,51 155,47 162,47"/>
            <polygon points="220,40 222,47 229,47 223,51 225,58 220,53 215,58 217,51 211,47 218,47"/>
            <polygon points="24,68 26,75 33,75 27,79 29,86 24,81 19,86 21,79 15,75 22,75"/>
            <polygon points="80,68 82,75 89,75 83,79 85,86 80,81 75,86 77,79 71,75 78,75"/>
            <polygon points="136,68 138,75 145,75 139,79 141,86 136,81 131,86 133,79 127,75 134,75"/>
            <polygon points="192,68 194,75 201,75 195,79 197,86 192,81 187,86 189,79 183,75 190,75"/>
            <polygon points="248,68 250,75 257,75 251,79 253,86 248,81 243,86 245,79 239,75 246,75"/>
          </g>
        </svg>
      );
    case 'AU':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="Australia Flag">
          <path fill="#000085" d="M0 0h640v480H0z"/>
          {/* Union Jack in canton */}
          <g transform="scale(0.5)">
            <path stroke="#FFF" strokeWidth="60" d="M0 0l640 480M640 0L0 480"/>
            <path stroke="#C8102E" strokeWidth="40" d="M0 0l640 480M640 0L0 480"/>
            <path stroke="#FFF" strokeWidth="100" d="M320 0v480M0 240h640"/>
            <path stroke="#C8102E" strokeWidth="60" d="M320 0v480M0 240h640"/>
          </g>
          {/* Large star */}
          <polygon fill="#FFFFFF" points="160,320 166,335 182,335 170,344 174,360 160,350 146,360 150,344 138,335 154,335"/>
          {/* Southern Cross */}
          <polygon fill="#FFFFFF" points="480,80 484,90 495,90 487,96 490,107 480,100 470,107 473,96 465,90 476,90"/>
          <polygon fill="#FFFFFF" points="480,380 484,390 495,390 487,396 490,407 480,400 470,407 473,396 465,390 476,390"/>
          <polygon fill="#FFFFFF" points="380,210 384,220 395,220 387,226 390,237 380,230 370,237 373,226 365,220 376,220"/>
          <polygon fill="#FFFFFF" points="560,180 564,190 575,190 567,196 570,207 560,200 550,207 553,196 545,190 556,190"/>
        </svg>
      );
    case 'CA':
      return (
        <svg className={className} viewBox="0 0 640 480" aria-label="Canada Flag">
          <path fill="#FF0000" d="M0 0h160v480H0zm480 0h160v480H480z"/>
          <path fill="#FFFFFF" d="M160 0h320v480H160z"/>
          <path fill="#FF0000" d="M320 100l22 45 42-12-18 45 45 18-35 30 18 50-44-18-5 52h-50l-5-52-44 18 18-50-35-30 45-18-18-45 42 12z"/>
        </svg>
      );
    default:
      return null;
  }
}
