/* Portfolio data for the "Selected work" section.
 * Plain JS array so the page also works when opened via file:// (no fetch needed).
 * All projects are fictional demo content created for this competition brand. */
(function (root) {
  'use strict';
  var PROJECTS = [
    {
      id: 'orbit-scheduler',
      title: 'Orbit Scheduler',
      category: 'Software',
      summary: 'A shift-planning tool that cut a clinic’s weekly rota work from hours to minutes.',
      tags: ['Automation', 'Web app'],
      image: 'assets/orbit.svg',
      alt: 'Abstract illustration of a blue planet with two small moons orbiting it'
    },
    {
      id: 'ledger-lens',
      title: 'Ledger Lens',
      category: 'AI integration',
      summary: 'Responsible AI that flags unusual invoices and explains why, for a small finance team.',
      tags: ['AI', 'Dashboards'],
      image: 'assets/ledger.svg',
      alt: 'Abstract illustration of five teal and mint bars of different heights'
    },
    {
      id: 'signal-studio',
      title: 'Signal Studio',
      category: 'Web design',
      summary: 'A calm, accessible redesign of a community radio station’s programme guide.',
      tags: ['Design system', 'Accessibility'],
      image: 'assets/signal.svg',
      alt: 'Abstract illustration of a purple wave line ending in a light dot'
    },
    {
      id: 'atlas-field-notes',
      title: 'Atlas Field Notes',
      category: 'Software',
      summary: 'An offline-first notes app for field surveyors that syncs when a connection returns.',
      tags: ['Offline-first', 'Mobile'],
      image: 'assets/atlas.svg',
      alt: 'Abstract illustration of orange mountain peaks'
    }
  ];
  if (typeof module !== 'undefined' && module.exports) { module.exports = PROJECTS; }
  root.NORTHSTAR_PROJECTS = PROJECTS;
})(typeof window !== 'undefined' ? window : globalThis);
