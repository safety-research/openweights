import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Container, Box, Button, Menu, MenuItem, IconButton } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { JobsView } from './components/JobsView';
import { RunsView } from './components/RunsView';
import { WorkersView } from './components/WorkersView';
import { JobDetailView, RunDetailView, WorkerDetailView } from './components/DetailViews';
import { Auth } from './components/Auth/Auth';
import { OrganizationsList } from './components/Organizations/OrganizationsList';
import { OrganizationDetail } from './components/Organizations/OrganizationDetail';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useState } from 'react';

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

function NavBar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleMenuItemClick = (path: string) => {
    handleMenuClose();
    if (path === 'logout') {
      signOut();
    } else {
      navigate(path);
    }
  };

  if (!user) return null;

  return (
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
        <Button color="inherit" component={Link} to="/jobs">Jobs</Button>
        <Button color="inherit" component={Link} to="/runs">Runs</Button>
        <Button color="inherit" component={Link} to="/workers">Workers</Button>
        <IconButton
          color="inherit"
          onClick={handleMenuClick}
          aria-label="more"
          aria-controls={open ? 'more-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          <MoreVertIcon />
        </IconButton>
        <Menu
          id="more-menu"
          anchorEl={anchorEl}
          open={open}
          onClose={handleMenuClose}
          MenuListProps={{
            'aria-labelledby': 'more-button',
          }}
        >
          <MenuItem onClick={() => handleMenuItemClick('/organizations')}>Organizations</MenuItem>
          <MenuItem onClick={() => handleMenuItemClick('logout')}>Logout</MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
}

function AppContent() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', width: '100%' }}>
      <NavBar />
      <Box component="main" sx={{ flexGrow: 1, width: '100%', height: '100%', overflow: 'auto' }}>
        <Container maxWidth={false} sx={{ mt: 3, mb: 3, height: 'calc(100vh - 84px)' }}>
          <Routes>
            <Route path="/login" element={<Auth />} />
            
            <Route path="/" element={<Navigate to="/jobs" />} />
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
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
}

export default App;