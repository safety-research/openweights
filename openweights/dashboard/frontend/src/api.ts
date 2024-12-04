import axios from 'axios';
import { Job, Run, Worker, JobWithRuns, RunWithJobAndWorker, WorkerWithRuns } from './types';
import { supabase } from './supabaseClient';

const API_URL = 'http://localhost:8124';

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

export const api = {
    // Jobs
    getJobs: async (status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Job[]>(`${API_URL}/jobs/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getJob: async (jobId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<JobWithRuns>(`${API_URL}/jobs/${jobId}`, config);
        return response.data;
    },
    
    // Runs
    getRuns: async (status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Run[]>(`${API_URL}/runs/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getRun: async (runId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<RunWithJobAndWorker>(`${API_URL}/runs/${runId}`, config);
        return response.data;
    },

    getRunLogs: async (runId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get(`${API_URL}/runs/${runId}/logs`, { 
            ...config,
            responseType: 'text'
        });
        return response.data;
    },
    
    // Workers
    getWorkers: async (status?: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<Worker[]>(`${API_URL}/workers/`, { 
            ...config,
            params: { status }
        });
        return response.data;
    },
    
    getWorker: async (workerId: string) => {
        const config = await getAuthHeaders();
        const response = await axios.get<WorkerWithRuns>(`${API_URL}/workers/${workerId}`, config);
        return response.data;
    },

    // Files
    getFileContent: async (fileId: string) => {
        const config = await getAuthHeaders();
        console.log('Fetching file content for:', fileId);
        const response = await axios.get(`${API_URL}/files/${fileId}/content`, {
            ...config,
            responseType: 'text'
        });
        console.log('File content response:', response.data);
        return response.data;
    },
};