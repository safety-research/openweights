import axios from 'axios';
import { Job, Run, Worker, JobWithRuns, RunWithJobAndWorker, WorkerWithRuns } from './types';

const API_URL = 'http://localhost:8124';

export const api = {
    // Jobs
    getJobs: async (status?: string) => {
        const response = await axios.get<Job[]>(`${API_URL}/jobs/`, { params: { status } });
        return response.data;
    },
    
    getJob: async (jobId: string) => {
        const response = await axios.get<JobWithRuns>(`${API_URL}/jobs/${jobId}`);
        return response.data;
    },
    
    // Runs
    getRuns: async (status?: string) => {
        const response = await axios.get<Run[]>(`${API_URL}/runs/`, { params: { status } });
        return response.data;
    },
    
    getRun: async (runId: string) => {
        const response = await axios.get<RunWithJobAndWorker>(`${API_URL}/runs/${runId}`);
        return response.data;
    },

    getRunLogs: async (runId: string) => {
        const response = await axios.get(`${API_URL}/runs/${runId}/logs`, { 
            responseType: 'text'
        });
        return response.data;
    },
    
    // Workers
    getWorkers: async (status?: string) => {
        const response = await axios.get<Worker[]>(`${API_URL}/workers/`, { params: { status } });
        return response.data;
    },
    
    getWorker: async (workerId: string) => {
        const response = await axios.get<WorkerWithRuns>(`${API_URL}/workers/${workerId}`);
        return response.data;
    },

    // Files
    getFileContent: async (fileId: string) => {
        console.log('Fetching file content for:', fileId);
        const response = await axios.get(`${API_URL}/files/${fileId}/content`, {
            responseType: 'text'
        });
        console.log('File content response:', response.data);
        return response.data;
    },
};