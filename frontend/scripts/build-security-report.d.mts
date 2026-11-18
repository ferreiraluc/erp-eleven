import type { Plugin } from 'vite'

export function buildSecurityReports(): { main: Plugin; worker: () => Plugin }
