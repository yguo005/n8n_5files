// Format Parent Email - HTML Version
// Outputs HTML-formatted email for better display in Gmail

// Get contact info from current json
const parentEmail = $json.parent_email || 'fallback@example.com';
const parentName = $json.parent_name || 'Parent';
const childName = $json.child_name || 'Child';

// Get summary output from summary node
let summaryContent = null;

try {
  const summaryNode = $('summary').first().json;
  
  if (typeof summaryNode.output === 'string') {
    summaryContent = { raw_text: summaryNode.output };
  } else if (typeof summaryNode.output === 'object') {
    summaryContent = summaryNode.output;
  }
} catch (e) {
  console.log('Error accessing summary node:', e.message);
}

// Convert markdown-style text to HTML
function markdownToHtml(text) {
  if (!text) return '';
  
  return text
    // Escape HTML special characters first
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Convert headers
    .replace(/^### (.+)$/gm, '<h3 style="color: #2c5282; margin-top: 20px; margin-bottom: 10px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="color: #2c5282; margin-top: 24px; margin-bottom: 12px;">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="color: #2c5282; margin-top: 28px; margin-bottom: 14px;">$1</h1>')
    // Convert bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Convert italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Convert bullet points
    .replace(/^- (.+)$/gm, '<li style="margin-bottom: 5px;">$1</li>')
    .replace(/^• (.+)$/gm, '<li style="margin-bottom: 5px;">$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li[^>]*>.*<\/li>\n?)+/g, '<ul style="margin: 10px 0; padding-left: 20px;">$&</ul>')
    // Convert numbered lists
    .replace(/^\d+\. (.+)$/gm, '<li style="margin-bottom: 5px;">$1</li>')
    // Convert line breaks (double newline = paragraph, single = <br>)
    .replace(/\n\n/g, '</p><p style="margin: 12px 0;">')
    .replace(/\n/g, '<br>');
}

// Build HTML email
let htmlContent = '';

if (summaryContent?.raw_text) {
  // Convert the raw LLM output to HTML
  const formattedContent = markdownToHtml(summaryContent.raw_text);
  
  htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      font-family: Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
    }
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 20px;
      border-radius: 8px 8px 0 0;
      text-align: center;
    }
    .content {
      background: #ffffff;
      padding: 25px;
      border: 1px solid #e2e8f0;
      border-top: none;
      border-radius: 0 0 8px 8px;
    }
    h3 {
      color: #2c5282;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 8px;
      margin-top: 25px;
    }
    .warning {
      background: #fff5f5;
      border-left: 4px solid #fc8181;
      padding: 12px 15px;
      margin: 15px 0;
      border-radius: 0 4px 4px 0;
    }
    .success {
      background: #f0fff4;
      border-left: 4px solid #68d391;
      padding: 12px 15px;
      margin: 15px 0;
      border-radius: 0 4px 4px 0;
    }
    .footer {
      text-align: center;
      padding: 20px;
      color: #718096;
      font-size: 12px;
      border-top: 1px solid #e2e8f0;
      margin-top: 20px;
    }
    ul, ol {
      margin: 10px 0;
      padding-left: 25px;
    }
    li {
      margin-bottom: 8px;
    }
  </style>
</head>
<body>
  <div class="header">
    <h1 style="margin: 0; font-size: 24px;">Clinical Summary Report</h1>
    <p style="margin: 10px 0 0 0; opacity: 0.9;">For ${childName}</p>
  </div>
  
  <div class="content">
    <p>Dear ${parentName},</p>
    <p>Please find below the clinical summary for ${childName}.</p>
    
    <div style="margin-top: 20px;">
      ${formattedContent}
    </div>
  </div>
  
  <div class="footer">
    <p>This summary was generated on ${new Date().toLocaleDateString()}.</p>
    <p>If you have questions, please contact your healthcare provider.</p>
  </div>
</body>
</html>`;

} else {
  // Fallback if no content found
  htmlContent = `
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
  <h2>Clinical Summary Report for ${childName}</h2>
  <p>Dear ${parentName},</p>
  <p>The clinical summary is currently being processed. Please check back later or contact your healthcare provider.</p>
</body>
</html>`;
}

return [{
  json: {
    to: parentEmail,
    subject: `Clinical Summary Report for ${childName}`,
    message: htmlContent,
    parent_name: parentName,
    child_name: childName
  }
}];