import React, { useEffect, useState, useCallback, Suspense, lazy } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
    Paper, 
    Typography, 
    Box, 
    Chip,
    FormControlLabel,
    Switch,
    Divider,
    CircularProgress,
    Button,
    Collapse
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { RunWithJobAndWorker } from '../../types';
import { api } from '../../api';
import { RefreshButton } from '../RefreshButton';
import { useOrganization } from '../../contexts/OrganizationContext';

// Lazy load components
const MetricsPlots = lazy(() => import('./MetricsPlots').then(module => ({ default: module.MetricsPlots })));
const LogProbVisualization = lazy(() => import('../LogProbVisualization').then(module => ({ default: module.LogProbVisualization })));

// Loading placeholder component
const LoadingPlaceholder = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
    </Box>
);

export const RunDetailView: React.FC = () => {
    const { orgId, runId } = useParams<{ orgId: string; runId: string }>();
    const { currentOrganization } = useOrganization();
    const [run, setRun] = useState<RunWithJobAndWorker | null>(null);
    const [logContent, setLogContent] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [events, setEvents] = useState<any[]>([]);

    // UI state for collapsible sections
    const [showMetrics, setShowMetrics] = useState(false);
    const [showLogProbs, setShowLogProbs] = useState(false);
    const [showLogs, setShowLogs] = useState(false);
    
    // Pagination for logs
    const [logPage, setLogPage] = useState(1);
    const logsPerPage = 1000; // Number of lines per page

    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchRun = useCallback(async () => {
        if (!orgId || !runId) return;
        setLoading(true);
        try {
            const data = await api.getRun(orgId, runId);
            setRun(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error in fetchRun:', error);
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    }, [orgId, runId]);

    // Separate function to fetch logs
    const fetchLogs = useCallback(async () => {
        if (!orgId || !runId) return;
        try {
            const logs = await api.getRunLogs(orgId, runId);
            setLogContent(logs);
        } catch (error) {
            console.error('Error fetching logs:', error);
        }
    }, [orgId, runId]);

    // Separate function to fetch events
    const fetchEvents = useCallback(async () => {
        if (!orgId || !runId) return;
        try {
            const runEvents = await api.getRunEvents(orgId, runId);
            setEvents(runEvents);
        } catch (error) {
            console.error('Error fetching events:', error);
        }
    }, [orgId, runId]);

    // Initial load
    useEffect(() => {
        fetchRun();
    }, [fetchRun]);

    // Auto-refresh effect
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh && run?.status === 'in_progress') {
            interval = setInterval(() => {
                fetchRun();
                if (showLogs) fetchLogs();
                if (showLogProbs || showMetrics) fetchEvents();
            }, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchRun, fetchLogs, fetchEvents, run?.status, showLogs, showLogProbs, showMetrics]);

    // Load section data when expanded
    useEffect(() => {
        if (showLogs) fetchLogs();
    }, [showLogs, fetchLogs]);

    useEffect(() => {
        if (showLogProbs || showMetrics) fetchEvents();
    }, [showLogProbs, showMetrics, fetchEvents]);

    // Filter logprob events and extract the data field
    const logprobEvents = events
        .filter(event => event.data?.type === 'logprobs')
        .map(event => event.data);

    if (!orgId || !currentOrganization || !run) {
        return <Typography>Loading...</Typography>;
    }

    if (!runId) {
        return <Typography>Run ID is required</Typography>;
    }

    // Paginate logs
    const paginatedLogs = logContent
        ? logContent
            .split('\n')
            .slice((logPage - 1) * logsPerPage, logPage * logsPerPage)
            .join('\n')
        : '';
    const totalLogPages = logContent
        ? Math.ceil(logContent.split('\n').length / logsPerPage)
        : 0;

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

            {/* Metrics Section */}
            <Box sx={{ mb: 2 }}>
                <Button
                    onClick={() => setShowMetrics(!showMetrics)}
                    endIcon={showMetrics ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    fullWidth
                >
                    Training Metrics
                </Button>
                <Collapse in={showMetrics}>
                    <Box sx={{ mt: 2 }}>
                        <Suspense fallback={<LoadingPlaceholder />}>
                            <MetricsPlots orgId={orgId} runId={runId} />
                        </Suspense>
                    </Box>
                </Collapse>
            </Box>

            {/* Log Probabilities Section */}
            {logprobEvents.length > 0 && (
                <Box sx={{ mb: 2 }}>
                    <Button
                        onClick={() => setShowLogProbs(!showLogProbs)}
                        endIcon={showLogProbs ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                        fullWidth
                    >
                        Log Probabilities ({logprobEvents.length} events)
                    </Button>
                    <Collapse in={showLogProbs}>
                        <Box sx={{ mt: 2 }}>
                            <Suspense fallback={<LoadingPlaceholder />}>
                                <LogProbVisualization 
                                    events={logprobEvents}
                                    orgId={orgId}
                                    getFileContent={(fileId: string) => api.getFileContent(orgId, fileId)}
                                />
                            </Suspense>
                        </Box>
                    </Collapse>
                </Box>
            )}

            {/* Logs Section */}
            <Box sx={{ mb: 2 }}>
                <Button
                    onClick={() => setShowLogs(!showLogs)}
                    endIcon={showLogs ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    fullWidth
                >
                    Log Output
                </Button>
                <Collapse in={showLogs}>
                    {logContent && (
                        <Box sx={{ mt: 2 }}>
                            <Paper 
                                sx={{ 
                                    p: 2, 
                                    bgcolor: 'grey.100',
                                    maxHeight: '500px',
                                    overflow: 'auto'
                                }}
                            >
                                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
                                    {paginatedLogs}
                                </pre>
                            </Paper>
                            {totalLogPages > 1 && (
                                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', gap: 2 }}>
                                    <Button 
                                        disabled={logPage === 1}
                                        onClick={() => setLogPage(p => Math.max(1, p - 1))}
                                    >
                                        Previous
                                    </Button>
                                    <Typography>
                                        Page {logPage} of {totalLogPages}
                                    </Typography>
                                    <Button 
                                        disabled={logPage === totalLogPages}
                                        onClick={() => setLogPage(p => Math.min(totalLogPages, p + 1))}
                                    >
                                        Next
                                    </Button>
                                </Box>
                            )}
                        </Box>
                    )}
                </Collapse>
            </Box>
        </Paper>
    );
};