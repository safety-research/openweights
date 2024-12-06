import axios from 'axios';
import { Job, Run, Worker, JobWithRuns, RunWithJobAndWorker, WorkerWithRuns, Organization } from './types';
import { supabase } from './supabaseClient';

// In production, use relative paths. In development, use localhost
const API_URL = import.meta.env.PROD ? '' : 'http://localhost:8124';

const getAuthHeaders = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) {
        throw new Error('No authentication token available');
    }
    
    return {
        headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
        }
    };
};

interface CreateOrganizationData {
    name: string;
    secrets: {
        HF_USER: string;
        HF_ORG: string;
        HF_TOKEN: string;
        RUNPOD_API_KEY: string;
    };
}

export const api = {
    // Organizations
    getOrganizations: async () => {
        const config = await getAuthHeaders();
        const response = await axios.get<Organization[]>(`${API_URL}/organizations/`, config);
        return response.data;
    },

    getOrganization: async (orgId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Organization>(`${API_URL}/organizations/${orgId}`, config);
        return response.data;
    },

    createOrganization: async (data: CreateOrganizationData) => {
        const config = await getAuthHeaders();
        const response = await axios.post<Organization>(`${API_URL}/organizations/`, data, config);
        return response.data;
    },
    
    // Jobs
    getJobs: async (orgId: string, status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Job[]>(`${API_URL}/organizations/${orgId}/jobs/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getJob: async (orgId: string, jobId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<JobWithRuns>(`${API_URL}/organizations/${orgId}/jobs/${jobId}`, config);
        return response.data;
    },
    
    // Runs
    getRuns: async (orgId: string, status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Run[]>(`${API_URL}/organizations/${orgId}/runs/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getRun: async (orgId: string, runId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<RunWithJobAndWorker>(`${API_URL}/organizations/${orgId}/runs/${runId}`, config);
        return response.data;
    },

    getRunLogs: async (orgId: string, runId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get(`${API_URL}/organizations/${orgId}/runs/${runId}/logs`, { 
            ...config,
            responseType: 'text'
        });
        return response.data;
    },
    
    // Workers
    getWorkers: async (orgId: string, status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Worker[]>(`${API_URL}/organizations/${orgId}/workers/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getWorker: async (orgId: string, workerId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<WorkerWithRuns>(`${API_URL}/organizations/${orgId}/workers/${workerId}`, config);
        return response.data;
    },

    // Files
    getFileContent: async (orgId: string, fileId: string) => {
        const config = await getAuthHeaders();
        console.log('Fetching file content for:', fileId);
        const response = await axios.get(`${API_URL}/organizations/${orgId}/files/${fileId}/content`, {
            ...config,
            responseType: 'text'
        });
        console.log('File content response:', response.data);
        return response.data;
    },

    // Tokens
    createToken: async (orgId: string, name: string, expiresInDays?: number) => {
        const config = await getAuthHeaders();
        const response = await axios.post(`${API_URL}/organizations/${orgId}/tokens`, {
            name,
            expires_in_days: expiresInDays
        }, config);
        return response.data;
    },

    listTokens: async (orgId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get(`${API_URL}/organizations/${orgId}/tokens`, config);
        return response.data;
    },

    deleteToken: async (orgId: string, tokenId: string) => {
        const config = await getAuthHeaders();
        await axios.delete(`${API_URL}/organizations/${orgId}/tokens/${tokenId}`, config);
    }
};