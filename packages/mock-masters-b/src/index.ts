import express from 'express';
import cors from 'cors';
import discoverRouter from './routes/discover.js';
import validateRouter from './routes/validate.js';
import uploadFileRouter from './routes/upload-file.js';
import submitDraftRouter from './routes/submit-draft.js';
import submitFinalRouter from './routes/submit-final.js';
import recordsRouter from './routes/records.js';

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3003;

// Middleware
app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'mock-masters-b', port: PORT });
});

// Mount all routes under /ai-agent/v1/
app.use('/ai-agent/v1', discoverRouter);
app.use('/ai-agent/v1', validateRouter);
app.use('/ai-agent/v1', uploadFileRouter);
app.use('/ai-agent/v1', submitDraftRouter);
app.use('/ai-agent/v1', submitFinalRouter);
app.use('/ai-agent/v1', recordsRouter);

app.listen(PORT, () => {
  console.log(`\n🤖 Westbrook AI Masters Mock API running at http://localhost:${PORT}`);
  console.log(`   Base URL: http://localhost:${PORT}/ai-agent/v1/`);
  console.log(`   Endpoints: /discover, /validate, /upload-file, /submit-draft, /submit-final, /drafts, /submissions\n`);
});

export default app;
