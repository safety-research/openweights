import React, { useEffect, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { 
    Grid, 
    Paper, 
    Typography, 
    Card, 
    CardContent, 
    Button, 
    Box,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TablePagination,
    FormControlLabel,
    Switch,
    Chip,
    Tooltip
} from '@mui/material';
import { Job, Run } from '../types';
import { api } from '../api';
import { RefreshButton } from './RefreshButton';
import { StatusCheckboxes, StatusFilters } from './StatusCheckboxes';
import { ViewToggle } from './ViewToggle';
import { JobsListView } from './JobsListView';
import { useOrganization } from '../contexts/OrganizationContext';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip as ChartTooltip,
    Legend
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    ChartTooltip,
    Legend
);

interface TrainingMetricsProps {
    orgId: string;
    jobId: string;
}

const TrainingMetrics: React.FC<TrainingMetricsProps> = ({ orgId, jobId }) => {
    const [metrics, setMetrics] = useState<{ step: number; loss: number }[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const runs = await api.getRuns(orgId);
                const jobRuns = runs.filter((run: Run) => run.job_id === jobId);
                if (jobRuns.length > 0) {
                    const latestRun = jobRuns.sort((a: Run, b: Run) =>
                        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                    )[0];

                    if (latestRun.status === 'completed') {
                        const events = await api.getRunEvents(orgId, latestRun.id);
                        const lossMetrics = events
                            .filter((event: { data: { type?: string; loss?: number; step?: number } }) =>
                                event.data.type === 'training' &&
                                event.data.loss !== undefined &&
                                event.data.step !== undefined
                            )
                            .map((event: { data: { step: number; loss: number } }) => ({
                                step: event.data.step,
                                loss: event.data.loss
                            }));
                        setMetrics(lossMetrics);
                    }
                }
            } catch (error) {
                console.error('Error fetching metrics:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchMetrics();
    }, [orgId, jobId]);

    if (loading || metrics.length === 0) {
        return null;
    }

    const data = {
        labels: metrics.map(m => m.step),
        datasets: [
            {
                label: 'Training Loss',
                data: metrics.map(m => m.loss),
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }
        ]
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                enabled: true
            }
        },
        scales: {
            x: {
                display: false
            },
            y: {
                display: false
            }
        }
    };

    return (
        <Box sx={{ width: 300, height: 150 }}>
            <Line data={data} options={options} />
        </Box>
    );
};

const JobCard: React.FC<{ job: Job; orgId: string }> = ({ job, orgId }) => {
    return (
    <Card 
        sx={{ 
            mb: 2,
            backgroundColor: '#ffffff',
            transition: 'background-color 0.3s ease',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}
    >
        <CardContent>
            <Typography variant="h6" component="div" color="text.primary">
                {job.id}
            </Typography>
            <Typography color="text.secondary">
                Type: {job.type}
            </Typography>
            {job.type === 'fine-tuning' && job.ft_id && (
                <Typography color="text.secondary">
                    Fine-tuning ID: {job.ft_id}
                </Typography>
            )}
            <Box sx={{ mt: 1, mb: 1 }}>
                <Chip 
                    label={job.status}
                    color={
                        job.status === 'completed' ? 'success' :
                        job.status === 'failed' ? 'error' :
                        job.status === 'canceled' ? 'warning' :
                        job.status === 'in_progress' ? 'info' :
                        'default'
                    }
                    size="small"
                />
            </Box>
            {job.model && (
                <Typography color="text.secondary">
                    Model: {job.model}
                </Typography>
            )}
            {job.docker_image && (
                <Typography color="text.secondary" sx={{ 
                    wordBreak: 'break-word'
                }}>
                    Image: {job.docker_image}
                </Typography>
            )}
            <Typography color="text.secondary" sx={{ mb: 1 }}>
                Created: {new Date(job.created_at).toLocaleString()}
            </Typography>
            <Link
                to={`/${orgId}/jobs/${job.id}`} 
                style={{
                    textDecoration: 'none',
                    display: 'inline-block',
                    marginTop: '8px'
                }}
            >
                <Button
                variant="outlined" 
            >
                View Details
            </Button>
            </Link>
        </CardContent>
    </Card>
);
};

// Wrap the JobCard with a tooltip for fine-tuning jobs
const JobCardWithTooltip: React.FC<{ job: Job; orgId: string }> = ({ job, orgId }) => {
    if (job.type === 'fine-tuning' && job.status === 'completed') {
        return (
            <Tooltip
                title={
                    <TrainingMetrics orgId={orgId} jobId={job.id} />
                }
                placement="right"
                arrow
            >
                <Box>
                    <JobCard job={job} orgId={orgId} />
                </Box>
            </Tooltip>
        );
    }
    return <JobCard job={job} orgId={orgId} />;
};

interface JobsColumnProps {
    title: string;
    jobs: Job[];
    filter: string;
    page: number;
    rowsPerPage: number;
    onPageChange: (newPage: number) => void;
    onRowsPerPageChange: (newRowsPerPage: number) => void;
    lastRefresh?: Date;
    onRefresh: () => void;
    loading?: boolean;
    orgId: string;
}

const JobsColumn: React.FC<JobsColumnProps> = ({ 
    title, 
    jobs, 
    filter,
    page,
    rowsPerPage,
    onPageChange,
    onRowsPerPageChange,
    lastRefresh,
    onRefresh,
    loading,
    orgId
}) => {
    const filteredJobs = jobs.filter(job => {
        const searchStr = filter.toLowerCase();
        const jobId = String(job.id);
        const model = job.model ? job.model.toLowerCase() : '';
        const dockerImage = job.docker_image ? job.docker_image.toLowerCase() : '';
        
        return jobId.includes(searchStr) ||
            model.includes(searchStr) ||
            dockerImage.includes(searchStr) ||
            JSON.stringify(job.params).toLowerCase().includes(searchStr) ||
            JSON.stringify(job.outputs).toLowerCase().includes(searchStr);
    });

    const paginatedJobs = filteredJobs.slice(
        page * rowsPerPage,
        page * rowsPerPage + rowsPerPage
    );

    return (
        <Grid item xs={12} md={4} sx={{ height: '100%' }}>
            <Paper 
                sx={{ 
                    p: 2, 
                    height: '100%', 
                    overflow: 'auto', 
                    display: 'flex', 
                    flexDirection: 'column',
                    backgroundColor: '#ffffff',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h5" sx={{ flexGrow: 1, color: 'text.primary' }}>
                        {title} ({filteredJobs.length})
                    </Typography>
                    <RefreshButton 
                        onRefresh={onRefresh}
                        loading={loading}
                        lastRefresh={lastRefresh}
                    />
                </Box>
                <Box sx={{ flexGrow: 1, overflow: 'auto', mb: 2 }}>
                    {paginatedJobs.map(job => (
                        <JobCardWithTooltip key={job.id} job={job} orgId={orgId} />
                    ))}
                </Box>
                <TablePagination
                    component="div"
                    count={filteredJobs.length}
                    page={page}
                    onPageChange={(_, newPage) => onPageChange(newPage)}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={(event) => onRowsPerPageChange(parseInt(event.target.value, 10))}
                    rowsPerPageOptions={[5, 10, 25]}
                />
            </Paper>
        </Grid>
    );
};

export const JobsView: React.FC = () => {
    const { orgId } = useParams<{ orgId: string }>();
    const { currentOrganization } = useOrganization();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [filter, setFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('all');
    const [pages, setPages] = useState({ pending: 0, inProgress: 0, completed: 0 });
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(false);
    const [view, setView] = useState<'three-column' | 'list'>('three-column');
    const [statusFilters, setStatusFilters] = useState<StatusFilters>({
        completed: true,
        failed: true,
        canceled: true
    });
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchJobs = useCallback(async () => {
        if (!orgId) return;
        
        setLoading(true);
        try {
            const data = await api.getJobs(orgId);
            // Sort by created_at descending
            data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
            setJobs(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching jobs:', error);
        } finally {
            setLoading(false);
        }
    }, [orgId]);

    useEffect(() => {
        fetchJobs();
    }, [fetchJobs]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh) {
            interval = setInterval(fetchJobs, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchJobs]);

    const handlePageChange = (status: string) => (newPage: number) => {
        setPages(prev => ({ ...prev, [status]: newPage }));
    };

    const handleRowsPerPageChange = (newRowsPerPage: number) => {
        setRowsPerPage(newRowsPerPage);
        setPages({ pending: 0, inProgress: 0, completed: 0 });
    };

    const filteredJobs = jobs.filter(job => {
        const matchesType = typeFilter === 'all' || job.type === typeFilter;
        return matchesType;
    });

    const pendingJobs = filteredJobs.filter(job => job.status === 'pending');
    const inProgressJobs = filteredJobs.filter(job => job.status === 'in_progress');
    const finishedJobs = filteredJobs.filter(job => {
        if (job.status === 'completed' && statusFilters.completed) return true;
        if (job.status === 'failed' && statusFilters.failed) return true;
        if (job.status === 'canceled' && statusFilters.canceled) return true;
        return false;
    });

    if (!orgId || !currentOrganization) {
        return <Typography>Loading...</Typography>;
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box 
                sx={{ 
                    mb: 3, 
                    display: 'flex', 
                    gap: 2, 
                    alignItems: 'center', 
                    flexWrap: 'wrap',
                    p: 2,
                    backgroundColor: '#ffffff',
                    borderRadius: 1,
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                }}
            >
                <TextField
                    label="Search"
                    variant="outlined"
                    size="small"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    sx={{ 
                        width: 200,
                        '& .MuiOutlinedInput-root': {
                            backgroundColor: '#ffffff',
                        }
                    }}
                />
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Type</InputLabel>
                    <Select
                        value={typeFilter}
                        label="Type"
                        onChange={(e) => setTypeFilter(e.target.value)}
                    >
                        <MenuItem value="all">All</MenuItem>
                        <MenuItem value="fine-tuning">Fine-tuning</MenuItem>
                        <MenuItem value="inference">Inference</MenuItem>
                        <MenuItem value="api">API</MenuItem>
                        <MenuItem value="script">Script</MenuItem>
                    </Select>
                </FormControl>
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
                <StatusCheckboxes
                    filters={statusFilters}
                    onChange={setStatusFilters}
                />
                <Box sx={{ ml: 'auto' }}>
                    <ViewToggle view={view} onViewChange={setView} />
                </Box>
            </Box>
            {view === 'three-column' ? (
                <Grid container spacing={3} sx={{ flexGrow: 1 }}>
                    <JobsColumn 
                        title="Pending" 
                        jobs={pendingJobs}
                        filter={filter}
                        page={pages.pending}
                        rowsPerPage={rowsPerPage}
                        onPageChange={handlePageChange('pending')}
                        onRowsPerPageChange={handleRowsPerPageChange}
                        lastRefresh={lastRefresh}
                        onRefresh={fetchJobs}
                        loading={loading}
                        orgId={orgId}
                    />
                    <JobsColumn 
                        title="In Progress" 
                        jobs={inProgressJobs}
                        filter={filter}
                        page={pages.inProgress}
                        rowsPerPage={rowsPerPage}
                        onPageChange={handlePageChange('inProgress')}
                        onRowsPerPageChange={handleRowsPerPageChange}
                        lastRefresh={lastRefresh}
                        onRefresh={fetchJobs}
                        loading={loading}
                        orgId={orgId}
                    />
                    <JobsColumn 
                        title="Finished" 
                        jobs={finishedJobs}
                        filter={filter}
                        page={pages.completed}
                        rowsPerPage={rowsPerPage}
                        onPageChange={handlePageChange('completed')}
                        onRowsPerPageChange={handleRowsPerPageChange}
                        lastRefresh={lastRefresh}
                        onRefresh={fetchJobs}
                        loading={loading}
                        orgId={orgId}
                    />
                </Grid>
            ) : (
                <JobsListView
                    jobs={[...pendingJobs, ...inProgressJobs, ...finishedJobs]}
                    filter={filter}
                    page={pages.completed}
                    rowsPerPage={rowsPerPage}
                    onPageChange={(_, newPage) => handlePageChange('completed')(newPage)}
                    onRowsPerPageChange={(event) => handleRowsPerPageChange(parseInt(event.target.value, 10))}
                    orgId={orgId}
                />
            )}
        </Box>
    );
};