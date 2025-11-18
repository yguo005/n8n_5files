import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { load } from "https://deno.land/std@0.208.0/dotenv/mod.ts";

// Load environment variables from .env file
const env = await load();

// Function to read the doctors note JSON file
async function readDoctorsNote() {
  try {
    const jsonText = await Deno.readTextFile("./doctors_note.json");
    const doctorsNote = JSON.parse(jsonText);
    return doctorsNote;
  } catch (error) {
    logError("Error reading doctors note:", error);
    return null;
  }
}
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"
};
const GROQ_API_KEY = Deno.env.get("GROQ_API_KEY");
const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";
const MODEL = "meta-llama/llama-4-scout-17b-16e-instruct";
// Error logger utility
function logError(msg, err) {
  console.error(msg, err instanceof Error ? err.message : err);
}
// Utility to convert a FormData File to base64 string for Groq API
async function fileToBase64(file) {
  // Deno File objects support arrayBuffer
  const buf = await file.arrayBuffer();
  // Convert ArrayBuffer to base64
  return btoa(String.fromCharCode(...new Uint8Array(buf)));
}
serve(async (req)=>{
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: corsHeaders
    });
  }

  // Add route to read doctors note JSON
  const url = new URL(req.url);
  if (req.method === "GET" && url.pathname === "/doctors-note") {
    try {
      const doctorsNote = await readDoctorsNote();
      if (doctorsNote) {
        return new Response(JSON.stringify(doctorsNote), {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      } else {
        return new Response(JSON.stringify({
          error: "Could not read doctors note file"
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
    } catch (error) {
      return new Response(JSON.stringify({
        error: "Error reading doctors note",
        detail: error.message
      }), {
        status: 500,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json"
        }
      });
    }
  }

  try {
    const contentType = req.headers.get("content-type") || "";
    const url = new URL(req.url);
    
    // If it's a multipart/form-data request with an image
    if (contentType.startsWith("multipart/form-data")) {
      // Read FormData
      const formData = await req.formData();
      const file = formData.get("file");
      if (!file) {
        return new Response(JSON.stringify({
          error: "Missing file upload."
        }), {
          status: 400,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      // 1. Send image to Groq for OCR (image to text)
      // Prepare Groq API call for image to text
      const imageBase64 = await fileToBase64(file);
      const ocrPrompt = [
        {
          role: "system",
          content: "You are a helpful assistant. Extract and return ALL clear, readable handwritten text from the image. Output only the text, no explanation, no formatting."
        },
        {
          role: "user",
          content: [
            {
              type: "image_url",
              image_url: {
                url: `data:${file.type};base64,${imageBase64}`
              }
            }
          ]
        }
      ];
      const ocrRes = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GROQ_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: ocrPrompt,
          max_tokens: 512,
          temperature: 0.1
        })
      });
      if (!ocrRes.ok) {
        const errorText = await ocrRes.text();
        logError('Groq OCR error:', errorText);
        return new Response(JSON.stringify({
          error: "Groq OCR API error",
          detail: errorText
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const ocrData = await ocrRes.json();
      const noteText = ocrData.choices && ocrData.choices[0]?.message?.content ? ocrData.choices[0].message.content.trim() : null;
      if (!noteText) {
        return new Response(JSON.stringify({
          error: "No text extracted from image."
        }), {
          status: 502,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      // 2A. SOAP conversion (Doctor version)
      const soapPrompt = [
        {
          role: "system",
          content: "You are a helpful assistant. Given a raw doctor's note (written in clinical language), convert it to a structured SOAP (Subjective, Objective, Assessment, Plan) format. Only output the SOAP structure in clear, labeled sections."
        },
        {
          role: "user",
          content: noteText
        }
      ];
      const groqSoapRes = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GROQ_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: soapPrompt,
          max_tokens: 512,
          temperature: 0.4,
          top_p: 1,
          stream: false
        })
      });
      if (!groqSoapRes.ok) {
        const errorText = await groqSoapRes.text();
        logError('Groq SOAP error:', errorText);
        return new Response(JSON.stringify({
          error: "Groq SOAP API error",
          detail: errorText
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const soapData = await groqSoapRes.json();
      const soapResult = soapData.choices && soapData.choices[0]?.message?.content ? soapData.choices[0].message.content.trim() : null;
      if (!soapResult) {
        return new Response(JSON.stringify({
          error: "No result from Groq SOAP conversion."
        }), {
          status: 502,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      // 2B. Patient-Friendly Summary
      const patientPrompt = [
        {
          role: "system",
          content: "You are a helpful assistant. Given a doctor's note or its extracted text, create a concise and friendly summary in simple, non-technical language, so that a patient can easily understand it. Avoid any medical jargon or technical terms. Be positive, reassuring, and brief."
        },
        {
          role: "user",
          content: noteText
        }
      ];
      const groqPatientRes = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GROQ_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: patientPrompt,
          max_tokens: 180,
          temperature: 0.6,
          top_p: 1,
          stream: false
        })
      });
      if (!groqPatientRes.ok) {
        const errorText = await groqPatientRes.text();
        logError('Groq Patient Summary error:', errorText);
        return new Response(JSON.stringify({
          error: "Groq Patient Summary API error",
          detail: errorText
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const patientData = await groqPatientRes.json();
      const patientSummary = patientData.choices && patientData.choices[0]?.message?.content ? patientData.choices[0].message.content.trim() : null;
      if (!patientSummary) {
        return new Response(JSON.stringify({
          error: "No result from Groq Patient Summary."
        }), {
          status: 502,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      return new Response(JSON.stringify({
        extracted_text: noteText,
        soap: soapResult,
        patient_summary: patientSummary
      }), {
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json"
        }
      });
    } else if (contentType.includes("application/json")) {
      // Fallback: JSON input with raw noteText (for text-only cases)
      let body;
      try {
        body = await req.json();
      } catch (jsonError) {
        return new Response(JSON.stringify({
          error: "Invalid JSON in request body"
        }), {
          status: 400,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const { noteText } = body;
      if (!noteText) {
        return new Response(JSON.stringify({
          error: "Missing noteText"
        }), {
          status: 400,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      // ... SOAP conversion code as before (text-only path)
      const soapPrompt = [
        {
          role: "system",
          content: "You are a helpful assistant. Given a raw doctor's note (written in clinical language), convert it to a structured SOAP (Subjective, Objective, Assessment, Plan) format. Only output the SOAP structure in clear, labeled sections."
        },
        {
          role: "user",
          content: noteText
        }
      ];
      const groqSoapRes = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GROQ_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: soapPrompt,
          max_tokens: 512,
          temperature: 0.4,
          top_p: 1,
          stream: false
        })
      });
      if (!groqSoapRes.ok) {
        const errorText = await groqSoapRes.text();
        logError('Groq SOAP (text) error:', errorText);
        return new Response(JSON.stringify({
          error: "Groq SOAP API error",
          detail: errorText
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const soapData = await groqSoapRes.json();
      const soapResult = soapData.choices && soapData.choices[0]?.message?.content ? soapData.choices[0].message.content.trim() : null;
      if (!soapResult) {
        return new Response(JSON.stringify({
          error: "No result from Groq API."
        }), {
          status: 502,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      // Patient Summary
      const patientPrompt = [
        {
          role: "system",
          content: "You are a helpful assistant. Given a doctor's note or its extracted text, create a concise and friendly summary in simple, non-technical language, so that a patient can easily understand it. Avoid any medical jargon or technical terms. Be positive, reassuring, and brief."
        },
        {
          role: "user",
          content: noteText
        }
      ];
      const groqPatientRes = await fetch(GROQ_API_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GROQ_API_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: MODEL,
          messages: patientPrompt,
          max_tokens: 180,
          temperature: 0.6,
          top_p: 1,
          stream: false
        })
      });
      if (!groqPatientRes.ok) {
        const errorText = await groqPatientRes.text();
        logError('Groq Patient Summary (text) error:', errorText);
        return new Response(JSON.stringify({
          error: "Groq Patient Summary API error",
          detail: errorText
        }), {
          status: 500,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      const patientData = await groqPatientRes.json();
      const patientSummary = patientData.choices && patientData.choices[0]?.message?.content ? patientData.choices[0].message.content.trim() : null;
      if (!patientSummary) {
        return new Response(JSON.stringify({
          error: "No result from Groq Patient Summary."
        }), {
          status: 502,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json"
          }
        });
      }
      return new Response(JSON.stringify({
        soap: soapResult,
        patient_summary: patientSummary
      }), {
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json"
        }
      });
    } else {
      // Unsupported content type
      return new Response(JSON.stringify({
        error: "Unsupported content type. Please use multipart/form-data for file uploads or application/json for text input."
      }), {
        status: 400,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json"
        }
      });
    }
  } catch (error) {
    logError("Edge function exception:", error);
    return new Response(JSON.stringify({
      error: "Internal server error"
    }), {
      status: 500,
      headers: {
        ...corsHeaders,
        "Content-Type": "application/json"
      }
    });
  }
});
