import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
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
    Switch,
    FormControlLabel
} from '@mui/material';
import { Run } from '../types';
import { api } from '../api';
import { RefreshButton } from './RefreshButton';

const getStatusColor = (status: string) => {
    switch (status) {
        case 'completed':
            return '#e6f4ea';  // light green
        case 'canceled':
            return '#fff8e1';  // light yellow
        case 'failed':
            return '#ffebee';  // light red
        default:
            return undefined;
    }
};

const RunCard: React.FC<{ run: Run }> = ({ run }) => (
    <Card 
        sx={{ 
            mb: 2,
            backgroundColor: getStatusColor(run.status),
            transition: 'background-color 0.3s ease'
        }}
    >
        <CardContent>
            <Typography variant="h6" component="div">
                {run.id}
            </Typography>
            <Typography color="text.secondary">
                Job: <Link to={`/jobs/${run.job_id}`}>{run.job_id}</Link>
            </Typography>
            <Typography color="text.secondary">
                Status: {run.status}
            </Typography>
            {run.worker_id && (
                <Typography color="text.secondary">
                    Worker: <Link to={`/workers/${run.worker_id}`}>{run.worker_id}</Link>
                </Typography>
            )}
            <Typography color="text.secondary" sx={{ mb: 1 }}>
                Created: {new Date(run.created_at).toLocaleString()}
            </Typography>
            <Button component={Link} to={`/runs/${run.id}`} variant="outlined" sx={{ mt: 1 }}>
                View Details
            </Button>
        </CardContent>
    </Card>
);

interface RunsColumnProps {
    title: string;
    runs: Run[];
    filter: string;
    page: number;
    rowsPerPage: number;
    onPageChange: (newPage: number) => void;
    onRowsPerPageChange: (newRowsPerPage: number) => void;
    lastRefresh?: Date;
    onRefresh: () => void;
    loading?: boolean;
}

const RunsColumn: React.FC<RunsColumnProps> = ({ 
    title, 
    runs, 
    filter,
    page,
    rowsPerPage,
    onPageChange,
    onRowsPerPageChange,
    lastRefresh,
    onRefresh,
    loading
}) => {
    const filteredRuns = runs.filter(run => {
        const searchStr = filter.toLowerCase();
        const runId = String(run.id);
        const jobId = String(run.job_id);
        const workerId = run.worker_id ? String(run.worker_id) : '';
        
        return runId.toLowerCase().includes(searchStr) ||
            jobId.toLowerCase().includes(searchStr) ||
            workerId.toLowerCase().includes(searchStr);
    });

    const paginatedRuns = filteredRuns.slice(
        page * rowsPerPage,
        page * rowsPerPage + rowsPerPage
    );

    return (
        <Grid item xs={12} md={4} sx={{ height: '100%' }}>
            <Paper sx={{ p: 2, height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h5" sx={{ flexGrow: 1 }}>
                        {title} ({filteredRuns.length})
                    </Typography>
                    <RefreshButton 
                        onRefresh={onRefresh}
                        loading={loading}
                        lastRefresh={lastRefresh}
                    />
                </Box>
                <Box sx={{ flexGrow: 1, overflow: 'auto', mb: 2 }}>
                    {paginatedRuns.map(run => (
                        <RunCard key={run.id} run={run} />
                    ))}
                </Box>
                <TablePagination
                    component="div"
                    count={filteredRuns.length}
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

export const RunsView: React.FC = () => {
    const [runs, setRuns] = useState<Run[]>([]);
    const [filter, setFilter] = useState('');
    const [pages, setPages] = useState({ pending: 0, inProgress: 0, completed: 0 });
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchRuns = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.getRuns();
            // Sort by created_at descending
            data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
            setRuns(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching runs:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRuns();
    }, [fetchRuns]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh) {
            interval = setInterval(fetchRuns, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchRuns]);

    const handlePageChange = (status: string) => (newPage: number) => {
        setPages(prev => ({ ...prev, [status]: newPage }));
    };

    const handleRowsPerPageChange = (newRowsPerPage: number) => {
        setRowsPerPage(newRowsPerPage);
        setPages({ pending: 0, inProgress: 0, completed: 0 });
    };

    const pendingRuns = runs.filter(run => run.status === 'pending');
    const inProgressRuns = runs.filter(run => run.status === 'in_progress');
    const completedRuns = runs.filter(run => ['completed', 'failed', 'canceled'].includes(run.status));

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
                <TextField
                    label="Search"
                    variant="outlined"
                    size="small"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    sx={{ 
                        width: 200,
                        '& .MuiOutlinedInput-root': {
                            backgroundColor: 'background.paper',
                            '& fieldset': {
                                borderColor: 'rgba(255, 255, 255, 0.23)',
                            },
                            '&:hover fieldset': {
                                borderColor: 'rgba(255, 255, 255, 0.4)',
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: 'primary.main',
                            },
                        },
                        '& .MuiInputLabel-root': {
                            color: 'text.secondary',
                        },
                        '& .MuiInputBase-input': {
                            color: 'text.primary',
                        },
                    }}
                />
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
            </Box>
            <Grid container spacing={3} sx={{ flexGrow: 1 }}>
                <RunsColumn 
                    title="Pending" 
                    runs={pendingRuns}
                    filter={filter}
                    page={pages.pending}
                    rowsPerPage={rowsPerPage}
                    onPageChange={handlePageChange('pending')}
                    onRowsPerPageChange={handleRowsPerPageChange}
                    lastRefresh={lastRefresh}
                    onRefresh={fetchRuns}
                    loading={loading}
                />
                <RunsColumn 
                    title="In Progress" 
                    runs={inProgressRuns}
                    filter={filter}
                    page={pages.inProgress}
                    rowsPerPage={rowsPerPage}
                    onPageChange={handlePageChange('inProgress')}
                    onRowsPerPageChange={handleRowsPerPageChange}
                    lastRefresh={lastRefresh}
                    onRefresh={fetchRuns}
                    loading={loading}
                />
                <RunsColumn 
                    title="Completed/Failed" 
                    runs={completedRuns}
                    filter={filter}
                    page={pages.completed}
                    rowsPerPage={rowsPerPage}
                    onPageChange={handlePageChange('completed')}
                    onRowsPerPageChange={handleRowsPerPageChange}
                    lastRefresh={lastRefresh}
                    onRefresh={fetchRuns}
                    loading={loading}
                />
            </Grid>
        </Box>
    );
};