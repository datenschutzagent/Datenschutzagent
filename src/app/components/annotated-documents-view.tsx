import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { 
  FileText, 
  Download, 
  MessageSquare,
  Highlighter,
  FileCheck
} from "lucide-react";

interface AnnotatedDocument {
  id: string;
  name: string;
  type: "docx" | "pdf";
  annotationCount: number;
  lastModified: string;
  comments: Array<{
    id: string;
    page?: number;
    section?: string;
    type: "comment" | "highlight" | "suggestion";
    severity: "critical" | "high" | "medium" | "low";
    text: string;
    context: string;
  }>;
}

const mockAnnotatedDocuments: AnnotatedDocument[] = [
  {
    id: "doc-003",
    name: "Probandeninformation_DE.pdf",
    type: "pdf",
    annotationCount: 3,
    lastModified: "2026-02-06T10:30:00",
    comments: [
      {
        id: "anno-001",
        page: 2,
        type: "highlight",
        severity: "critical",
        text: "Speicherdauer fehlt",
        context: "Die Information zur Speicherdauer der Daten ist gemäß Art. 13 Abs. 2 lit. a DSGVO eine Pflichtangabe und fehlt hier.",
      },
      {
        id: "anno-002",
        page: 1,
        section: "Absatz 3",
        type: "comment",
        severity: "high",
        text: "Rechtsgrundlage inkonsistent",
        context: "Hier wird von 'Einwilligung' gesprochen, im VVT ist jedoch Art. 6 Abs. 1 lit. e DSGVO angegeben. Bitte Konsistenz herstellen.",
      },
      {
        id: "anno-003",
        page: 3,
        type: "suggestion",
        severity: "medium",
        text: "Widerrufsrecht präzisieren",
        context: "Das Widerrufsrecht sollte explizit formuliert werden: 'Sie können Ihre Einwilligung jederzeit ohne Angabe von Gründen widerrufen.'",
      },
    ],
  },
  {
    id: "doc-004",
    name: "Participant_Information_EN.pdf",
    type: "pdf",
    annotationCount: 2,
    lastModified: "2026-02-06T10:30:00",
    comments: [
      {
        id: "anno-101",
        page: 2,
        type: "highlight",
        severity: "critical",
        text: "Storage duration missing",
        context: "Please add information about how long the data will be stored (e.g., '10 years after project completion').",
      },
      {
        id: "anno-102",
        page: 3,
        type: "comment",
        severity: "medium",
        text: "Right to withdraw consent",
        context: "Please clarify: 'You can withdraw your consent at any time without giving reasons. The withdrawal does not affect the lawfulness of processing based on consent before its withdrawal.'",
      },
    ],
  },
  {
    id: "doc-001",
    name: "VVT_Burnout_Studie_v2.docx",
    type: "docx",
    annotationCount: 4,
    lastModified: "2026-02-06T10:30:00",
    comments: [
      {
        id: "anno-201",
        section: "Zeile 24",
        type: "comment",
        severity: "high",
        text: "AVV für US-Empfänger fehlt",
        context: "Bei 'CloudProvider Inc., USA' als Empfänger ist ein Auftragsverarbeitungsvertrag (AVV) sowie Drittlandtransfer-Garantien (z.B. SCCs) erforderlich.",
      },
      {
        id: "anno-202",
        section: "Zeile 26",
        type: "highlight",
        severity: "critical",
        text: "Speicherdauer nicht ausgefüllt",
        context: "Dieses Pflichtfeld muss ausgefüllt werden. Bitte konkrete Zeiträume oder Kriterien angeben.",
      },
      {
        id: "anno-203",
        section: "Zeile 15",
        type: "comment",
        severity: "high",
        text: "Rechtsgrundlage prüfen",
        context: "Art. 6 Abs. 1 lit. e DSGVO ist angegeben, jedoch wird im Informationsblatt von 'Einwilligung' gesprochen. Bitte klären.",
      },
      {
        id: "anno-204",
        section: "Zeile 19",
        type: "suggestion",
        severity: "medium",
        text: "Kategorien präzisieren",
        context: "Die Angabe 'Gesundheitsdaten' ist korrekt. Optional: konkrete Subkategorien ergänzen (z.B. 'Burnout-Scores').",
      },
    ],
  },
];

export function AnnotatedDocumentsView() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <MessageSquare className="size-8 text-purple-600" />
              </div>
              <div>
                <CardTitle>Kommentierte Dokumente</CardTitle>
                <CardDescription className="mt-1">
                  Automatisch generierte Annotationen zur Rückgabe an Forschende
                </CardDescription>
              </div>
            </div>
            <Button className="gap-2">
              <Download className="size-4" />
              Alle herunterladen
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Document List */}
      <div className="grid gap-6">
        {mockAnnotatedDocuments.map((doc) => (
          <Card key={doc.id}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <FileText className="size-6 text-blue-600 mt-1" />
                  <div>
                    <CardTitle className="text-lg">{doc.name}</CardTitle>
                    <CardDescription className="flex items-center gap-3 mt-1">
                      <Badge variant="outline">{doc.type.toUpperCase()}</Badge>
                      <span>{doc.annotationCount} Annotationen</span>
                      <span>•</span>
                      <span>
                        Aktualisiert: {new Date(doc.lastModified).toLocaleDateString("de-DE")}
                      </span>
                    </CardDescription>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="gap-2">
                    <Download className="size-4" />
                    Download
                  </Button>
                  <Button variant="outline" size="sm" className="gap-2">
                    <FileCheck className="size-4" />
                    Vorschau
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="all">
                <TabsList className="mb-4">
                  <TabsTrigger value="all">Alle ({doc.comments.length})</TabsTrigger>
                  <TabsTrigger value="critical">
                    Kritisch ({doc.comments.filter(c => c.severity === "critical").length})
                  </TabsTrigger>
                  <TabsTrigger value="high">
                    Hoch ({doc.comments.filter(c => c.severity === "high").length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="all" className="space-y-3">
                  {doc.comments.map((comment) => (
                    <AnnotationCard key={comment.id} comment={comment} />
                  ))}
                </TabsContent>

                <TabsContent value="critical" className="space-y-3">
                  {doc.comments
                    .filter(c => c.severity === "critical")
                    .map((comment) => (
                      <AnnotationCard key={comment.id} comment={comment} />
                    ))}
                </TabsContent>

                <TabsContent value="high" className="space-y-3">
                  {doc.comments
                    .filter(c => c.severity === "high")
                    .map((comment) => (
                      <AnnotationCard key={comment.id} comment={comment} />
                    ))}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Export Options */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export-Optionen</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button variant="outline" className="w-full justify-start gap-2">
            <FileText className="size-4" />
            DOCX mit Track Changes & Kommentaren
          </Button>
          <Button variant="outline" className="w-full justify-start gap-2">
            <FileText className="size-4" />
            PDF mit Annotationen (Highlights & Notes)
          </Button>
          <Button variant="outline" className="w-full justify-start gap-2">
            <Download className="size-4" />
            JSON (maschinenlesbare Findings)
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function AnnotationCard({ comment }: { comment: AnnotatedDocument["comments"][0] }) {
  const severityColors = {
    critical: "border-red-200 bg-red-50",
    high: "border-orange-200 bg-orange-50",
    medium: "border-yellow-200 bg-yellow-50",
    low: "border-blue-200 bg-blue-50",
  };

  const severityBadgeColors = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-blue-100 text-blue-700",
  };

  const typeIcons = {
    comment: MessageSquare,
    highlight: Highlighter,
    suggestion: FileCheck,
  };

  const TypeIcon = typeIcons[comment.type];

  return (
    <div className={`p-4 border rounded-lg ${severityColors[comment.severity]}`}>
      <div className="flex items-start gap-3">
        <TypeIcon className="size-5 mt-0.5 text-slate-600" />
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="font-medium text-slate-900">{comment.text}</h4>
            <Badge className={severityBadgeColors[comment.severity]}>
              {comment.severity}
            </Badge>
            <Badge variant="outline" className="text-xs capitalize">
              {comment.type}
            </Badge>
          </div>
          
          {comment.page && (
            <p className="text-xs text-slate-600 mb-2">
              📄 Seite {comment.page}
              {comment.section && ` • ${comment.section}`}
            </p>
          )}
          {!comment.page && comment.section && (
            <p className="text-xs text-slate-600 mb-2">
              📍 {comment.section}
            </p>
          )}

          <p className="text-sm text-slate-700 bg-white/50 p-2 rounded border border-slate-200">
            {comment.context}
          </p>
        </div>
      </div>
    </div>
  );
}