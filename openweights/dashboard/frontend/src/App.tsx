import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Container, Box, Button } from '@mui/material';
import { JobsView } from './components/JobsView';
import { RunsView } from './components/RunsView';
import { WorkersView } from './components/WorkersView';
import { AllView } from './components/AllView';
import { JobDetailView, RunDetailView, WorkerDetailView } from './components/DetailViews';

function App() {
  return (
    <Router>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', width: '100%' }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              OpenWeights Dashboard
            </Typography>
            <Button color="inherit" component={Link} to="/all">All</Button>
            <Button color="inherit" component={Link} to="/jobs">Jobs</Button>
            <Button color="inherit" component={Link} to="/runs">Runs</Button>
            <Button color="inherit" component={Link} to="/workers">Workers</Button>
          </Toolbar>
        </AppBar>

        <Box component="main" sx={{ flexGrow: 1, width: '100%', height: '100%', overflow: 'auto' }}>
          <Container maxWidth={false} sx={{ mt: 3, mb: 3, height: 'calc(100vh - 84px)' }}>
            <Routes>
              <Route path="/" element={<AllView />} />
              <Route path="/all" element={<AllView />} />
              <Route path="/jobs" element={<JobsView />} />
              <Route path="/jobs/:jobId" element={<JobDetailView />} />
              <Route path="/runs" element={<RunsView />} />
              <Route path="/runs/:runId" element={<RunDetailView />} />
              <Route path="/workers" element={<WorkersView />} />
              <Route path="/workers/:workerId" element={<WorkerDetailView />} />
            </Routes>
          </Container>
        </Box>
      </Box>
    </Router>
  );
}

export default App;