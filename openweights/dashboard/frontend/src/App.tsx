import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Container, Box, Button } from '@mui/material';
import { JobsView } from './components/JobsView';
import { RunsView } from './components/RunsView';
import { WorkersView } from './components/WorkersView';
import { AllView } from './components/AllView';
import { JobDetailView, RunDetailView, WorkerDetailView } from './components/DetailViews';
import { Login } from './components/Auth/Login';
import { OrganizationsList } from './components/Organizations/OrganizationsList';
import { OrganizationDetail } from './components/Organizations/OrganizationDetail';
import { AuthProvider, useAuth } from './contexts/AuthContext';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <Typography>Loading...</Typography>;
  }
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  return <>{children}</>;
}

function AppContent() {
  const { user, signOut } = useAuth();

  return (
    <Router>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', width: '100%' }}>
        <AppBar position="static">
          <Toolbar>
            <img
              src="/ow.svg"
              alt="OpenWeights Logo"
              style={{
                height: '32px',
                width: '32px',
                marginRight: '12px'
              }}
            />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              OpenWeights Dashboard
            </Typography>
            {user && (
              <>
                <Button color="inherit" component={Link} to="/all">All</Button>
                <Button color="inherit" component={Link} to="/jobs">Jobs</Button>
                <Button color="inherit" component={Link} to="/runs">Runs</Button>
                <Button color="inherit" component={Link} to="/workers">Workers</Button>
                <Button color="inherit" component={Link} to="/organizations">Organizations</Button>
                <Button color="inherit" onClick={() => signOut()}>Logout</Button>
              </>
            )}
          </Toolbar>
        </AppBar>

        <Box component="main" sx={{ flexGrow: 1, width: '100%', height: '100%', overflow: 'auto' }}>
          <Container maxWidth={false} sx={{ mt: 3, mb: 3, height: 'calc(100vh - 84px)' }}>
            <Routes>
              <Route path="/login" element={<Login />} />
              
              <Route path="/" element={<PrivateRoute><AllView /></PrivateRoute>} />
              <Route path="/all" element={<PrivateRoute><AllView /></PrivateRoute>} />
              <Route path="/jobs" element={<PrivateRoute><JobsView /></PrivateRoute>} />
              <Route path="/jobs/:jobId" element={<PrivateRoute><JobDetailView /></PrivateRoute>} />
              <Route path="/runs" element={<PrivateRoute><RunsView /></PrivateRoute>} />
              <Route path="/runs/:runId" element={<PrivateRoute><RunDetailView /></PrivateRoute>} />
              <Route path="/workers" element={<PrivateRoute><WorkersView /></PrivateRoute>} />
              <Route path="/workers/:workerId" element={<PrivateRoute><WorkerDetailView /></PrivateRoute>} />
              <Route path="/organizations" element={<PrivateRoute><OrganizationsList /></PrivateRoute>} />
              <Route path="/organizations/:id" element={<PrivateRoute><OrganizationDetail /></PrivateRoute>} />
            </Routes>
          </Container>
        </Box>
      </Box>
    </Router>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;