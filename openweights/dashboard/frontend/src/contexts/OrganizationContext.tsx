import { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Organization } from '../types';
import { api } from '../api';
import { useAuth } from './AuthContext';

interface OrganizationContextType {
  organizations: Organization[];
  currentOrganization: Organization | null;
  setCurrentOrganization: (org: Organization) => void;
  loadOrganizations: () => Promise<void>;
  loading: boolean;
}

const OrganizationContext = createContext<OrganizationContextType | null>(null);

export function OrganizationProvider({ children }: { children: React.ReactNode }) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrganization, setCurrentOrganization] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const loadOrganizations = async () => {
    try {
      setLoading(true);
      const orgs = await api.getOrganizations();
      setOrganizations(orgs);

      // If we have organizations but none selected, and we're not on the organizations page,
      // redirect to organization selection
      if (orgs.length > 0 && !currentOrganization && location.pathname !== '/organizations') {
        navigate('/organizations');
      }

      setLoading(false);
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setLoading(false);
    }
  };

  // Load organizations when user changes
  useEffect(() => {
    if (user) {
      loadOrganizations();
    } else {
      setOrganizations([]);
      setCurrentOrganization(null);
    }
  }, [user]);

  // Try to extract organization ID from URL and set it as current
  useEffect(() => {
    const match = location.pathname.match(/^\/([^/]+)/);
    if (match && match[1] !== 'organizations' && match[1] !== 'login') {
      const orgId = match[1];
      const org = organizations.find(o => o.id === orgId);
      if (org && (!currentOrganization || currentOrganization.id !== org.id)) {
        setCurrentOrganization(org);
      }
    }
  }, [location.pathname, organizations]);

  const handleSetOrganization = (org: Organization) => {
    setCurrentOrganization(org);
    // If we're on the organizations page, navigate to jobs
    if (location.pathname === '/organizations') {
      navigate(`/${org.id}/jobs`);
    }
  };

  return (
    <OrganizationContext.Provider 
      value={{
        organizations,
        currentOrganization,
        setCurrentOrganization: handleSetOrganization,
        loadOrganizations,
        loading
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}

export const useOrganization = () => {
  const context = useContext(OrganizationContext);
  if (!context) {
    throw new Error('useOrganization must be used within an OrganizationProvider');
  }
  return context;
};