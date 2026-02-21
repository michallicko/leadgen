/**
 * Default Tiptap JSON content for a new GTM Strategy document.
 *
 * Contains 8 strategic sections as H2 headings, each with a placeholder
 * paragraph providing guidance on what to write.
 */

import type { JSONContent } from '@tiptap/react'

function heading(level: 1 | 2 | 3, text: string): JSONContent {
  return {
    type: 'heading',
    attrs: { level },
    content: [{ type: 'text', text }],
  }
}

function paragraph(text: string): JSONContent {
  return {
    type: 'paragraph',
    content: [{ type: 'text', text }],
  }
}

export const STRATEGY_TEMPLATE: JSONContent = {
  type: 'doc',
  content: [
    heading(1, 'GTM Strategy'),

    heading(2, 'Executive Summary'),
    paragraph(
      'A brief overview of your go-to-market approach, key objectives, and expected outcomes.',
    ),

    heading(2, 'Ideal Customer Profile (ICP)'),
    paragraph(
      'Define your target market segments, company characteristics (size, industry, geography), and the signals that indicate a good fit.',
    ),

    heading(2, 'Buyer Personas'),
    paragraph(
      'Describe the key decision-makers and influencers you target. Include their titles, responsibilities, goals, and pain points.',
    ),

    heading(2, 'Value Proposition'),
    paragraph(
      'Articulate why your solution matters. What problem does it solve? What makes it unique compared to alternatives?',
    ),

    heading(2, 'Competitive Positioning'),
    paragraph(
      'Map out your competitive landscape. Where do you win, where do you lose, and how do you differentiate?',
    ),

    heading(2, 'Channel Strategy'),
    paragraph(
      'Outline your outreach channels (LinkedIn, email, events, partnerships) and the role each plays in your pipeline.',
    ),

    heading(2, 'Messaging Framework'),
    paragraph(
      'Define core messaging themes, tone of voice, and key talking points for each persona and channel.',
    ),

    heading(2, 'Success Metrics'),
    paragraph(
      'List the KPIs that measure strategy effectiveness: conversion rates, pipeline velocity, deal sizes, and engagement benchmarks.',
    ),
  ],
}
