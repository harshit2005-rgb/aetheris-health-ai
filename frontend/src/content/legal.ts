export interface LegalDoc {
  slug: string
  title: string
  updated: string
  intro: string
  sections: { heading: string; body: string[] }[]
}

const CONTACT_LINE =
  'Questions about this page can be sent to our privacy team via the Contact page.'

export const privacyDoc: LegalDoc = {
  slug: 'privacy',
  title: 'Privacy Policy',
  updated: 'August 2026',
  intro:
    'This policy explains what information Aetheris Health AI collects, how we use it, and the choices you have. It applies to our marketing site and clinical platform.',
  sections: [
    {
      heading: 'Information we collect',
      body: [
        'Account information you provide, such as your name, work email, and organization.',
        'Usage data about how the platform is used, collected to keep the service secure and reliable.',
      ],
    },
    {
      heading: 'Protected health information',
      body: [
        'When your organization uses Aetheris to process patient data, we act as a Business Associate under HIPAA and handle that data only as instructed by your organization and the governing agreement.',
      ],
    },
    {
      heading: 'How we use information',
      body: [
        'To provide, maintain, and improve the platform, to secure it against misuse, and to support your team.',
        'We do not sell personal information, and we do not use patient data to train models outside the bounds of your agreement.',
      ],
    },
    {
      heading: 'Data security',
      body: [
        'Data is encrypted in transit and at rest, access is role-based, and every access is logged. See the HIPAA Compliance page for details on our safeguards.',
      ],
    },
    {
      heading: 'Data retention',
      body: [
        'We retain information for as long as your account is active or as needed to provide the service, then delete or de-identify it in line with your agreement and applicable law.',
      ],
    },
    {
      heading: 'Your rights',
      body: [
        'Depending on your location, you may request access to, correction of, or deletion of your personal information. Contact us to exercise these rights.',
      ],
    },
    {
      heading: 'Changes to this policy',
      body: [
        'We may update this policy from time to time. Material changes will be communicated to account administrators.',
        CONTACT_LINE,
      ],
    },
  ],
}

export const termsDoc: LegalDoc = {
  slug: 'terms',
  title: 'Terms of Service',
  updated: 'August 2026',
  intro:
    'These terms govern your access to and use of the Aetheris Health AI platform. By using the service, your organization agrees to them.',
  sections: [
    {
      heading: 'The service',
      body: [
        'Aetheris provides clinical decision-support software. It surfaces analysis and recommendations to assist qualified clinicians.',
      ],
    },
    {
      heading: 'Clinical responsibility',
      body: [
        'Aetheris is a decision-support tool, not a substitute for professional medical judgment. A qualified clinician is responsible for every diagnosis and treatment decision.',
      ],
    },
    {
      heading: 'Accounts and eligibility',
      body: [
        'You are responsible for keeping account credentials secure and for activity under your account. Accounts are for authorized clinical staff only.',
      ],
    },
    {
      heading: 'Acceptable use',
      body: [
        'You agree not to misuse the service, attempt to access it without authorization, or use it in violation of applicable law or your organization policies.',
      ],
    },
    {
      heading: 'Intellectual property',
      body: [
        'Aetheris and its software are owned by Aetheris Health AI. These terms do not transfer any ownership in the platform to you.',
      ],
    },
    {
      heading: 'Disclaimers and liability',
      body: [
        'The service is provided on an as-available basis. To the extent permitted by law, Aetheris is not liable for indirect or consequential damages arising from use of the service.',
      ],
    },
    {
      heading: 'Changes to these terms',
      body: [
        'We may update these terms and will notify account administrators of material changes.',
        CONTACT_LINE,
      ],
    },
  ],
}

export const hipaaDoc: LegalDoc = {
  slug: 'hipaa',
  title: 'HIPAA Compliance',
  updated: 'August 2026',
  intro:
    'Aetheris Health AI is built to support HIPAA compliance for the healthcare organizations we serve. This page summarizes how we handle protected health information (PHI).',
  sections: [
    {
      heading: 'Our role as a Business Associate',
      body: [
        'When your organization processes PHI through Aetheris, we act as a Business Associate and enter into a Business Associate Agreement (BAA) that governs how we handle that data.',
      ],
    },
    {
      heading: 'Administrative safeguards',
      body: [
        'Documented security policies, workforce training, access management, and regular risk assessments govern how our team handles PHI.',
      ],
    },
    {
      heading: 'Physical and technical safeguards',
      body: [
        'PHI is encrypted in transit and at rest, access is granted on a least-privilege basis, and infrastructure can be deployed in your private cloud or on-premise.',
        'Every access to PHI is recorded in immutable audit logs.',
      ],
    },
    {
      heading: 'Breach notification',
      body: [
        'In the unlikely event of a breach affecting PHI, we notify affected organizations without undue delay and in line with HIPAA requirements and the BAA.',
      ],
    },
    {
      heading: 'Patient rights',
      body: [
        'We support covered entities in fulfilling patient rights to access and amend their records by keeping PHI accurate, available, and exportable.',
      ],
    },
    {
      heading: 'Audits and certifications',
      body: [
        'Our controls are independently audited. Documentation, including our latest SOC 2 report, is available to customers under NDA.',
        'To request our BAA or compliance documentation, reach out through the Contact page.',
      ],
    },
  ],
}

export const legalDocs: Record<string, LegalDoc> = {
  privacy: privacyDoc,
  terms: termsDoc,
  hipaa: hipaaDoc,
}
