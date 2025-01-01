import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
    Paper, 
    Typography, 
    Box, 
    Chip,
    FormControlLabel,
    Switch
} from '@mui/material';
import { RunWithJobAndWorker } from '../../types';
import { api } from '../../api';
import { RefreshButton } from '../RefreshButton';
import { useOrganization } from '../../contexts/OrganizationContext';

export const RunDetailView: React.FC = () => {
    const { orgId, runId } = useParams<{ orgId: string; runId: string }>();
    const { currentOrganization } = useOrganization();
    const [run, setRun] = useState<RunWithJobAndWorker | null>(null);
    const [logContent, setLogContent] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchRun = useCallback(async () => {
        if (!orgId || !runId) return;
        setLoading(true);
        try {
            const data = await api.getRun(orgId, runId);
            setRun(data);
            
            const logs = await api.getRunLogs(orgId, runId);
            setLogContent(logs);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error in fetchRun:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            setError(errorMessage);
            setLogContent('Error loading log file content: ' + errorMessage);
        } finally {
            setLoading(false);
        }
    }, [orgId, runId]);

    useEffect(() => {
        fetchRun();
    }, [fetchRun]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh && run?.status === 'in_progress') {
            interval = setInterval(fetchRun, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchRun, run?.status]);

    if (!orgId || !currentOrganization || !run) {
        return <Typography>Loading...</Typography>;
    }

    return (
        <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" sx={{ flexGrow: 1 }}>Run: {run.id}</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <FormControlLabel
                        control={
                            <Switch
                                checked={autoRefresh}
                                onChange={(e) => setAutoRefresh(e.target.checked)}
                                name="autoRefresh"
                            />
                        }
                        label="Auto-refresh"
                    />
                    <RefreshButton 
                        onRefresh={fetchRun}
                        loading={loading}
                        lastRefresh={lastRefresh}
                    />
                </Box>
            </Box>

            <Box sx={{ mb: 3 }}>
                <Chip label={`Status: ${run.status}`} sx={{ mr: 1 }} />
                <Chip 
                    label={`Job: ${run.job_id}`} 
                    component={Link} 
                    to={`/${orgId}/jobs/${run.job_id}`}
                    clickable
                    sx={{ mr: 1 }}
                />
                {run.worker && (
                    <Chip 
                        label={`Worker: ${run.worker_id}`}
                        component={Link}
                        to={`/${orgId}/workers/${run.worker_id}`}
                        clickable
                        sx={{ mr: 1 }}
                    />
                )}
            </Box>

            {error && (
                <Box sx={{ mb: 3 }}>
                    <Typography color="error">Error: {error}</Typography>
                </Box>
            )}

            {logContent && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="h6">Log Output:</Typography>
                    <Paper 
                        sx={{ 
                            p: 2, 
                            bgcolor: 'grey.100',
                            maxHeight: '500px',
                            overflow: 'auto'
                        }}
                    >
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                            {logContent}
                        </pre>
                    </Paper>
                </Box>
            )}
        </Paper>
    );
};