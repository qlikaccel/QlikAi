/**
 * API Configuration
 * Supports both local development and remote deployment
 */

const getApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000';
    }
    
    // Render production deployment
    // Map frontend domain to backend domain
    // qliksense-xd7f.onrender.com -> qlik-backend-demo.onrender.com
    // qliksense-demo.onrender.com -> qlik-backend-demo.onrender.com
    if (hostname.includes('onrender.com')) {
      // Use the hardcoded backend domain for Render
      return 'https://qliksense-demo.onrender.com';
    }
  }
  
  // Fallback
  return 'http://127.0.0.1:8000';
};

export const API_BASE_URL = getApiBaseUrl();

/**
 * Helper function to construct API endpoints
 * Usage: getApiUrl('/api/app/123/schema/base64')
 */
export const getApiUrl = (path: string): string => {
  return `${API_BASE_URL}${path}`;
};

// Export common endpoints
export const API_ENDPOINTS = {
  schemaBase64: (appId: string) => getApiUrl(`/api/app/${appId}/schema/base64`),
  powerbiProcess: () => getApiUrl('/powerbi/process'),
  powerbiLogin: {
    initiate: () => getApiUrl('/powerbi/login/initiate'),
    acquire: () => getApiUrl('/powerbi/login/acquire-token'),
    status: () => getApiUrl('/powerbi/login/status'),
    test: () => getApiUrl('/powerbi/login/test'),
  },
  reportDownloadPdf: () => getApiUrl('/report/download-pdf'),
};
