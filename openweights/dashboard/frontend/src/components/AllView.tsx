import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { 
    Paper, 
    Typography, 
    Button, 
    Box,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    FormControlLabel,
    Switch
} from '@mui/material';
import { Job, Run, Worker } from '../types';
import { api } from '../api';
import { RefreshButton } from './RefreshButton';

interface Item {
    id: string;
    type: 'job' | 'run' | 'worker';
    status: string;
    created_at: string;
    details: Job | Run | Worker;
}

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

export const AllView: React.FC = () => {
    const [items, setItems] = useState<Item[]>([]);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [filter, setFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [loading, setLoading] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date>();
    const [autoRefresh, setAutoRefresh] = useState(true);
    const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [jobs, runs, workers] = await Promise.all([
                api.getJobs(),
                api.getRuns(),
                api.getWorkers()
            ]);

            const allItems: Item[] = [
                ...jobs.map(job => ({
                    id: String(job.id),
                    type: 'job' as const,
                    status: job.status,
                    created_at: job.created_at,
                    details: job
                })),
                ...runs.map(run => ({
                    id: String(run.id),
                    type: 'run' as const,
                    status: run.status,
                    created_at: run.created_at,
                    details: run
                })),
                ...workers.map(worker => ({
                    id: String(worker.id),
                    type: 'worker' as const,
                    status: worker.status,
                    created_at: worker.created_at,
                    details: worker
                }))
            ];

            // Sort by created_at descending
            allItems.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
            setItems(allItems);
            setLastRefresh(new Date());
        } catch (error) {
            console.error('Error fetching data:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
    }, [fetchAll]);

    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (autoRefresh) {
            interval = setInterval(fetchAll, AUTO_REFRESH_INTERVAL);
        }
        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [autoRefresh, fetchAll]);

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    const filteredItems = items.filter(item => {
        const searchStr = filter.toLowerCase();
        const matchesSearch = item.id.toLowerCase().includes(searchStr);
        const matchesType = typeFilter === 'all' || item.type === typeFilter;
        const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
        return matchesSearch && matchesType && matchesStatus;
    });

    const paginatedItems = filteredItems.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant="h4" sx={{ flexGrow: 1 }}>All Items</Typography>
                <RefreshButton 
                    onRefresh={fetchAll}
                    loading={loading}
                    lastRefresh={lastRefresh}
                />
            </Box>
            
            <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
                <TextField
                    label="Search by ID"
                    variant="outlined"
                    size="small"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                />
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Type</InputLabel>
                    <Select
                        value={typeFilter}
                        label="Type"
                        onChange={(e) => setTypeFilter(e.target.value)}
                    >
                        <MenuItem value="all">All</MenuItem>
                        <MenuItem value="job">Jobs</MenuItem>
                        <MenuItem value="run">Runs</MenuItem>
                        <MenuItem value="worker">Workers</MenuItem>
                    </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <InputLabel>Status</InputLabel>
                    <Select
                        value={statusFilter}
                        label="Status"
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <MenuItem value="all">All</MenuItem>
                        <MenuItem value="pending">Pending</MenuItem>
                        <MenuItem value="in_progress">In Progress</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="failed">Failed</MenuItem>
                        <MenuItem value="canceled">Canceled</MenuItem>
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
            </Box>

            <TableContainer sx={{ flexGrow: 1 }}>
                <Table stickyHeader>
                    <TableHead>
                        <TableRow>
                            <TableCell>ID</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Created At</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {paginatedItems.map((item) => (
                            <TableRow 
                                key={`${item.type}-${item.id}`}
                                sx={{ backgroundColor: getStatusColor(item.status) }}
                            >
                                <TableCell>{item.id}</TableCell>
                                <TableCell>{item.type}</TableCell>
                                <TableCell>{item.status}</TableCell>
                                <TableCell>
                                    {new Date(item.created_at).toLocaleString()}
                                </TableCell>
                                <TableCell>
                                    <Button 
                                        component={Link} 
                                        to={`/${item.type}s/${item.id}`} 
                                        variant="outlined" 
                                        size="small"
                                    >
                                        View Details
                                    </Button>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>

            <TablePagination
                rowsPerPageOptions={[5, 10, 25, 50]}
                component="div"
                count={filteredItems.length}
                rowsPerPage={rowsPerPage}
                page={page}
                onPageChange={handleChangePage}
                onRowsPerPageChange={handleChangeRowsPerPage}
            />
        </Paper>
    );
};