/**
 * API Configuration
 * Supports both local development and remote deployment
 */

const getApiBaseUrl = (): string => {
  // For remote deployment (Render, Vercel, etc)
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // If running on Render or any remote domain
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      // Replace frontend domain with backend domain
      // Example: qliksense-xd7f.onrender.com -> qlik-backend.onrender.com
      const domain = hostname.replace('qliksense', 'qlik-backend');
      return `https://${domain}`;
    }
  }
  
  // Local development - use localhost
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
