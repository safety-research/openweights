import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
    Paper, 
    Typography, 
    Box, 
    Chip, 
    List, 
    ListItem, 
    ListItemText, 
    CircularProgress,
    FormControlLabel,
    Switch
} from '@mui/material';
import { JobWithRuns, RunWithJobAndWorker, WorkerWithRuns } from '../types';
import { api } from '../api';
import { RefreshButton } from './RefreshButton';
import { useOrganization } from '../contexts/OrganizationContext';

const FileContent: React.FC<{ fileId: string; orgId: string }> = ({ fileId, orgId }) => {
    const [content, setContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchContent = async () => {
            try {
                const data = await api.getFileContent(orgId, fileId);
                setContent(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load file content');
            } finally {
                setLoading(false);
            }
        };
        fetchContent();
    }, [fileId, orgId]);

    if (loading) return <CircularProgress size={20} />;
    if (error) return <Typography color="error">{error}</Typography>;
    if (!content) return <Typography>No content available</Typography>;

    return (
        <Paper sx={{ p: 2, bgcolor: 'grey.100', mt: 1 }}>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                {content}
            </pre>
        </Paper>
    );
};

const isFileId = (key: string, value: any): boolean => {
    if (typeof value !== 'string') return false;
    return key.toLowerCase().includes('file') || 
           value.toString().startsWith('file-') ||
           value.toString().includes(':file-');
};

const formatMetricValue = (value: any): string => {
    if (typeof value === 'number') {
        // Format small numbers in scientific notation
        if (Math.abs(value) < 0.0001 && value !== 0) {
            return value.toExponential(6);
        }
        // Format regular numbers with up to 6 decimal places
        return value.toFixed(6).replace(/\.?0+$/, '');
    }
    return String(value);
};

const MetricsDisplay: React.FC<{ metrics: Record<string, any> }> = ({ metrics }) => {
    // Group metrics by category
    const groups: Record<string, string[]> = {
        'Training': ['loss', 'nll_loss', 'eval_loss', 'eval_nll_loss', 'grad_norm', 'learning_rate'],
        'Progress': ['step', 'epoch'],
        'GPU': ['gpu_name', 'gpu_memory_free_mb', 'gpu_memory_reserved_mb', 'gpu_memory_allocated_mb'],
        'Model Outputs': [
            'logps/chosen', 'logps/rejected',
            'logits/chosen', 'logits/rejected',
            'log_odds_ratio', 'log_odds_chosen'
        ],
        'Rewards': [
            'rewards/chosen', 'rewards/rejected',
            'rewards/margins', 'rewards/accuracies'
        ],
        'Evaluation': [
            'eval_runtime', 'eval_steps_per_second',
            'eval_samples_per_second'
        ]
    };

    // Collect metrics by group
    const groupedMetrics: Record<string, Record<string, any>> = {};
    const ungroupedMetrics: Record<string, any> = {};

    Object.entries(metrics).forEach(([key, value]) => {
        let grouped = false;
        for (const [group, keys] of Object.entries(groups)) {
            if (keys.includes(key) || keys.some(k => key.startsWith(k))) {
                groupedMetrics[group] = groupedMetrics[group] || {};
                groupedMetrics[group][key] = value;
                grouped = true;
                break;
            }
        }
        if (!grouped) {
            ungroupedMetrics[key] = value;
        }
    });

    return (
        <Box>
            {Object.entries(groupedMetrics).map(([group, metrics]) => (
                metrics && Object.keys(metrics).length > 0 && (
                    <Box key={group} sx={{ mb: 3 }}>
                        <Typography variant="h6">{group}:</Typography>
                        <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                            {Object.entries(metrics).map(([key, value]) => (
                                <Typography key={key} sx={{ fontFamily: 'monospace' }}>
                                    {key}: {formatMetricValue(value)}
                                </Typography>
                            ))}
                        </Paper>
                    </Box>
                )
            ))}
            {Object.keys(ungroupedMetrics).length > 0 && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="h6">Other:</Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                        {Object.entries(ungroupedMetrics).map(([key, value]) => (
                            <Typography key={key} sx={{ fontFamily: 'monospace' }}>
                                {key}: {formatMetricValue(value)}
                            </Typography>
                        ))}
                    </Paper>
                </Box>
            )}
        </Box>
    );
};

const OutputsDisplay: React.FC<{ outputs: any; orgId: string }> = ({ outputs, orgId }) => {
    if (!outputs) return null;

    // Check if outputs is a metrics object (has numeric values) or contains file references
    const hasMetrics = Object.values(outputs).some(value => typeof value === 'number');

    if (hasMetrics) {
        return <MetricsDisplay metrics={outputs} />;
    }

    return (
        <Box>
            {Object.entries(outputs).map(([key, value]) => {
                if (isFileId(key, value)) {
                    return (
                        <Box key={key} sx={{ mb: 2 }}>
                            <Typography variant="subtitle1">{key}:</Typography>
                            <FileContent fileId={value as string} orgId={orgId} />
                        </Box>
                    );
                }

                if (typeof value === 'object') {
                    return (
                        <Box key={key} sx={{ mb: 2 }}>
                            <Typography variant="subtitle1">{key}:</Typography>
                            <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                                    {JSON.stringify(value, null, 2)}
                                </pre>
                            </Paper>
                        </Box>
                    );
                }

                return (
                    <Box key={key} sx={{ mb: 2 }}>
                        <Typography variant="subtitle1">{key}:</Typography>
                        <Typography>{String(value)}</Typography>
                    </Box>
                );
            })}
        </Box>
    );
};

export const JobDetailView: React.FC = () => {
    const { orgId, jobId } = useParams<{ orgId: string; jobId: string }>();
    const { currentOrganization } = useOrganization();
    const [job, setJob] = useState<JobWithRuns | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchJob = useCallback(async () => {
        if (!orgId || !jobId) return;
        setLoading(true);
        try {
            const data = await api.getJob(orgId, jobId);
            setJob(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching job:', error);
        } finally {
            setLoading(false);
        }
    }, [orgId, jobId]);

    useEffect(() => {
        fetchJob();
    }, [fetchJob]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh && job?.status === 'in_progress') {
            interval = setInterval(fetchJob, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchJob, job?.status]);

    if (!orgId || !currentOrganization || !job) {
        return <Typography>Loading...</Typography>;
    }

    return (
        <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" sx={{ flexGrow: 1 }}>Job: {job.id}</Typography>
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
                        onRefresh={fetchJob}
                        loading={loading}
                        lastRefresh={lastRefresh}
                    />
                </Box>
            </Box>
            
            <Box sx={{ mb: 3 }}>
                <Chip label={`Status: ${job.status}`} sx={{ mr: 1 }} />
                <Chip label={`Type: ${job.type}`} sx={{ mr: 1 }} />
                {job.model && <Chip label={`Model: ${job.model}`} sx={{ mr: 1 }} />}
                {job.docker_image && <Chip label={`Image: ${job.docker_image}`} sx={{ mr: 1 }} />}
            </Box>
            
            {job.script && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="h6">Script:</Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                            {job.script}
                        </pre>
                    </Paper>
                </Box>
            )}
            
            {job.params && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="h6">Parameters:</Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                            {JSON.stringify(job.params, null, 2)}
                        </pre>
                    </Paper>
                </Box>
            )}

            {job.outputs && (
                <Box sx={{ mb: 3 }}>
                    <Typography variant="h6">Outputs:</Typography>
                    <OutputsDisplay outputs={job.outputs} orgId={orgId} />
                </Box>
            )}

            <Typography variant="h6">Runs:</Typography>
            <List>
                {job.runs
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .map(run => (
                        <ListItem key={run.id} component={Link} to={`/${orgId}/runs/${run.id}`}>
                            <ListItemText 
                                primary={run.id}
                                secondary={`Status: ${run.status}, Created: ${new Date(run.created_at).toLocaleString()}`}
                            />
                        </ListItem>
                    ))
                }
            </List>
        </Paper>
    );
};

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

export const WorkerDetailView: React.FC = () => {
    const { orgId, workerId } = useParams<{ orgId: string; workerId: string }>();
    const { currentOrganization } = useOrganization();
    const [worker, setWorker] = useState<WorkerWithRuns | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchWorker = useCallback(async () => {
        if (!orgId || !workerId) return;
        setLoading(true);
        try {
            const data = await api.getWorker(orgId, workerId);
            setWorker(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching worker:', error);
        } finally {
            setLoading(false);
        }
    }, [orgId, workerId]);

    useEffect(() => {
        fetchWorker();
    }, [fetchWorker]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh && worker?.status === 'active') {
            interval = setInterval(fetchWorker, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchWorker, worker?.status]);

    if (!orgId || !currentOrganization || !worker) {
        return <Typography>Loading...</Typography>;
    }

    return (
        <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" sx={{ flexGrow: 1 }}>Worker: {worker.id}</Typography>
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
                        onRefresh={fetchWorker}
                        loading={loading}
                        lastRefresh={lastRefresh}
                    />
                </Box>
            </Box>

            <Box sx={{ mb: 3 }}>
                <Chip label={`Status: ${worker.status}`} sx={{ mr: 1 }} />
                {worker.gpu_type && (
                    <Chip label={`GPU: ${worker.gpu_type} (${worker.vram_gb}GB)`} sx={{ mr: 1 }} />
                )}
                {worker.docker_image && (
                    <Chip label={`Image: ${worker.docker_image}`} sx={{ mr: 1 }} />
                )}
            </Box>

            <Typography variant="h6">Run History:</Typography>
            <List>
                {worker.runs
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .map(run => (
                        <ListItem key={run.id} component={Link} to={`/${orgId}/runs/${run.id}`}>
                            <ListItemText 
                                primary={run.id}
                                secondary={`Status: ${run.status}, Job: ${run.job_id}, Created: ${new Date(run.created_at).toLocaleString()}`}
                            />
                        </ListItem>
                    ))
                }
            </List>
        </Paper>
    );
};