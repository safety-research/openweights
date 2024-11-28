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
    FormControlLabel,
    Switch
} from '@mui/material';
import { Job } from '../types';
import { api } from '../api';
import { RefreshButton } from './RefreshButton';
import { StatusCheckboxes, StatusFilters } from './StatusCheckboxes';

const getStatusColor = (status: string) => {
    switch (status) {
        case 'completed':
            return '#e6f4ea';  // light green
        case 'canceled':
            return '#fff8e1';  // light yellow
        case 'failed':
            return '#ffebee';  // light red
        default:
            return '#ffffff';  // white for other statuses
    }
};

const JobCard: React.FC<{ job: Job }> = ({ job }) => (
    <Card 
        sx={{ 
            mb: 2,
            backgroundColor: getStatusColor(job.status),
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
            <Typography color="text.secondary">
                Status: {job.status}
            </Typography>
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
            <Button 
                component={Link} 
                to={`/jobs/${job.id}`} 
                variant="outlined" 
                sx={{ mt: 1 }}
            >
                View Details
            </Button>
        </CardContent>
    </Card>
);

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
}

const searchInObject = (obj: any, searchStr: string): boolean => {
    if (!obj) return false;
    
    return Object.entries(obj).some(([key, value]) => {
        if (typeof value === 'string') {
            return value.toLowerCase().includes(searchStr);
        }
        if (typeof value === 'object') {
            return searchInObject(value, searchStr);
        }
        if (value !== null && value !== undefined) {
            return String(value).toLowerCase().includes(searchStr);
        }
        return false;
    });
};

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
    loading
}) => {
    const filteredJobs = jobs.filter(job => {
        const searchStr = filter.toLowerCase();
        const jobId = String(job.id);
        const model = job.model ? job.model.toLowerCase() : '';
        const dockerImage = job.docker_image ? job.docker_image.toLowerCase() : '';
        
        return jobId.includes(searchStr) ||
            model.includes(searchStr) ||
            dockerImage.includes(searchStr) ||
            searchInObject(job.params, searchStr) ||
            searchInObject(job.outputs, searchStr);
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
                        <JobCard key={job.id} job={job} />
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
    const [jobs, setJobs] = useState<Job[]>([]);
    const [filter, setFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('all');
    const [pages, setPages] = useState({ pending: 0, inProgress: 0, completed: 0 });
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [statusFilters, setStatusFilters] = useState<StatusFilters>({
        completed: true,
        failed: true,
        canceled: true
    });
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchJobs = useCallback(async () => {
        setLoading(true);
        try {
            const data = await api.getJobs();
            // Sort by created_at descending
            data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
            setJobs(data);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching jobs:', error);
        } finally {
            setLoading(false);
        }
    }, []);

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
    const completedJobs = filteredJobs.filter(job => {
        if (job.status === 'completed' && statusFilters.completed) return true;
        if (job.status === 'failed' && statusFilters.failed) return true;
        if (job.status === 'canceled' && statusFilters.canceled) return true;
        return false;
    });

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
            </Box>
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
                />
                <JobsColumn 
                    title="Completed/Failed/Canceled" 
                    jobs={completedJobs}
                    filter={filter}
                    page={pages.completed}
                    rowsPerPage={rowsPerPage}
                    onPageChange={handlePageChange('completed')}
                    onRowsPerPageChange={handleRowsPerPageChange}
                    lastRefresh={lastRefresh}
                    onRefresh={fetchJobs}
                    loading={loading}
                />
            </Grid>
        </Box>
    );
};