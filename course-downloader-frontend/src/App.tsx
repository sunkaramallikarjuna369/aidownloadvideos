import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Checkbox } from '@/components/ui/checkbox'
import { Download, FileVideo, Folder, CheckCircle, AlertCircle, Loader2, ChevronDown, ChevronRight, Play, RefreshCw } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
interface Video { title: string; url: string; module: string; chapter: string; lesson_id: string }
interface Chapter { name: string; videos: Video[]; video_count: number }
interface Module { name: string; chapters: Chapter[]; total_videos: number }
interface DownloadProgress { status: string; total_items: number; completed_items: number; current_item: string; errors: string[]; download_path?: string }

function App() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [videos, setVideos] = useState<Video[]>([])
  const [modules, setModules] = useState<Module[]>([])
  const [totalVideos, setTotalVideos] = useState(0)
  const [downloadPath, setDownloadPath] = useState('')
  const [downloadId, setDownloadId] = useState('')
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [expandedModules, setExpandedModules] = useState<string[]>([])
  const [expandedChapters, setExpandedChapters] = useState<string[]>([])
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set())

  useEffect(() => { loadVideoUrls() }, [])

  const loadVideoUrls = async () => {
    setIsLoading(true); setError('')
    try {
      const response = await fetch(`${API_URL}/api/load-video-urls`)
      const data = await response.json()
      if (data.success) {
        setVideos(data.videos || []); setModules(data.modules || [])
        setTotalVideos(data.total_videos || 0)
        setSuccess(`Loaded ${data.total_videos} videos from ${data.modules?.length || 0} modules`)
      } else { setError(data.detail || 'Failed to load') }
    } catch { setError('Failed to connect to server') }
    finally { setIsLoading(false) }
  }

  const getModuleVideos = (m: string) => videos.filter(v => v.module === m)
  const getChapterVideos = (m: string, c: string) => videos.filter(v => v.module === m && v.chapter === c)

  const isModuleSelected = (m: string): boolean | 'indeterminate' => {
    const mv = getModuleVideos(m); const sc = mv.filter(v => selectedVideos.has(v.lesson_id)).length
    return sc === 0 ? false : sc === mv.length ? true : 'indeterminate'
  }

  const isChapterSelected = (m: string, c: string): boolean | 'indeterminate' => {
    const cv = getChapterVideos(m, c); const sc = cv.filter(v => selectedVideos.has(v.lesson_id)).length
    return sc === 0 ? false : sc === cv.length ? true : 'indeterminate'
  }

  const toggleModule = (m: string) => {
    const mv = getModuleVideos(m); const all = isModuleSelected(m) === true
    setSelectedVideos(p => { const n = new Set(p); mv.forEach(v => all ? n.delete(v.lesson_id) : n.add(v.lesson_id)); return n })
  }

  const toggleChapter = (m: string, c: string) => {
    const cv = getChapterVideos(m, c); const all = isChapterSelected(m, c) === true
    setSelectedVideos(p => { const n = new Set(p); cv.forEach(v => all ? n.delete(v.lesson_id) : n.add(v.lesson_id)); return n })
  }

  const toggleVideo = (id: string) => setSelectedVideos(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n })
  const selectAll = () => setSelectedVideos(new Set(videos.map(v => v.lesson_id)))
  const deselectAll = () => setSelectedVideos(new Set())

  const handleDownloadSelected = async () => {
    if (selectedVideos.size === 0) { setError('Select at least one video'); return }
    setIsDownloading(true); setError(''); setSuccess('')
    try {
      const sv = videos.filter(v => selectedVideos.has(v.lesson_id))
      const r = await fetch(`${API_URL}/api/download-selected-videos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ download_path: downloadPath, videos: sv })
      })
      const d = await r.json()
      if (d.success) { setDownloadId(d.download_id); setSuccess(`Started downloading ${d.total_videos} videos`) }
      else { setError(d.detail || 'Failed'); setIsDownloading(false) }
    } catch { setError('Failed to start'); setIsDownloading(false) }
  }

  useEffect(() => {
    let i: NodeJS.Timeout
    if (downloadId && isDownloading) {
      i = setInterval(async () => {
        try {
          const r = await fetch(`${API_URL}/api/download/progress/${downloadId}`)
          const d = await r.json(); setDownloadProgress(d)
          if (d.status === 'completed' || d.status === 'error') { setIsDownloading(false); clearInterval(i) }
        } catch {}
      }, 1000)
    }
    return () => { if (i) clearInterval(i) }
  }, [downloadId, isDownloading])

  const toggleModuleExpand = (m: string) => setExpandedModules(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m])
  const toggleChapterExpand = (c: string) => setExpandedChapters(p => p.includes(c) ? p.filter(x => x !== c) : [...p, c])
  const expandAll = () => { setExpandedModules(modules.map(m => m.name)); setExpandedChapters(modules.flatMap(m => m.chapters.map(c => `${m.name}|${c.name}`))) }
  const collapseAll = () => { setExpandedModules([]); setExpandedChapters([]) }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">QpiAI Course Video Downloader</h1>
          <p className="text-purple-200">Select modules, chapters, or individual videos to download</p>
        </div>
        <Card className="max-w-5xl mx-auto bg-white/10 backdrop-blur-lg border-white/20 shadow-2xl">
          <CardHeader className="border-b border-white/10">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-2xl text-white flex items-center gap-2"><Play className="h-6 w-6 text-pink-400" />Course Videos</CardTitle>
                <CardDescription className="text-purple-200">{totalVideos > 0 ? <>{totalVideos} videos | {selectedVideos.size} selected</> : 'Loading...'}</CardDescription>
              </div>
              <Button onClick={loadVideoUrls} disabled={isLoading} variant="outline" className="border-white/30 text-white hover:bg-white/10">
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            <div className="bg-white/5 rounded-xl p-4 space-y-4">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <Label htmlFor="dp" className="text-white font-medium">Download Location</Label>
                  <Input id="dp" placeholder="D:\Downloads\QpiAI (leave empty for default)" value={downloadPath} onChange={e => setDownloadPath(e.target.value)} className="mt-1 bg-white/10 border-white/20 text-white placeholder:text-white/50" />
                </div>
                <div className="flex items-end">
                  <Button onClick={handleDownloadSelected} disabled={isDownloading || selectedVideos.size === 0} className="bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white px-8" size="lg">
                    {isDownloading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" />Downloading...</> : <><Download className="mr-2 h-5 w-5" />Download ({selectedVideos.size})</>}
                  </Button>
                </div>
              </div>
              {downloadProgress && (
                <div className="space-y-2 p-4 bg-black/20 rounded-lg">
                  <div className="flex justify-between text-sm text-white"><span>Progress: {downloadProgress.completed_items}/{downloadProgress.total_items}</span><Badge>{downloadProgress.status}</Badge></div>
                  <Progress value={downloadProgress.total_items > 0 ? (downloadProgress.completed_items / downloadProgress.total_items) * 100 : 0} className="h-3" />
                  {downloadProgress.current_item && <p className="text-sm text-purple-200 truncate">Downloading: {downloadProgress.current_item}</p>}
                  {downloadProgress.status === 'completed' && <Alert className="bg-green-500/20 border-green-500/50 mt-2"><CheckCircle className="h-4 w-4 text-green-400" /><AlertTitle className="text-green-300">Complete!</AlertTitle><AlertDescription className="text-green-200">All videos downloaded.{downloadProgress.download_path && <span className="block">Location: {downloadProgress.download_path}</span>}</AlertDescription></Alert>}
                </div>
              )}
            </div>
            {error && <Alert variant="destructive" className="bg-red-500/20 border-red-500/50"><AlertCircle className="h-4 w-4" /><AlertTitle>Error</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
            {success && !downloadProgress && <Alert className="bg-green-500/20 border-green-500/50"><CheckCircle className="h-4 w-4 text-green-400" /><AlertTitle className="text-green-300">Success</AlertTitle><AlertDescription className="text-green-200">{success}</AlertDescription></Alert>}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Course Structure</h3>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={selectAll} className="border-white/30 text-white hover:bg-white/10">Select All</Button>
                <Button size="sm" variant="outline" onClick={deselectAll} className="border-white/30 text-white hover:bg-white/10">Deselect All</Button>
                <Button size="sm" variant="outline" onClick={expandAll} className="border-white/30 text-white hover:bg-white/10">Expand All</Button>
                <Button size="sm" variant="outline" onClick={collapseAll} className="border-white/30 text-white hover:bg-white/10">Collapse All</Button>
              </div>
            </div>
            {isLoading ? <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-purple-400" /><span className="ml-3 text-purple-200">Loading...</span></div>
            : modules.length === 0 ? <div className="text-center py-12 text-purple-200"><Folder className="h-12 w-12 mx-auto mb-4 opacity-50" /><p>No videos found.</p></div>
            : <ScrollArea className="h-[500px] rounded-lg border border-white/10"><div className="p-4 space-y-2">
              {modules.map((mod, mi) => {
                const ms = isModuleSelected(mod.name)
                return <div key={mi} className="bg-white/5 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-3 p-3 hover:bg-white/5">
                    <Checkbox checked={ms === true} onCheckedChange={() => toggleModule(mod.name)} className="border-white/50 data-[state=checked]:bg-pink-500" />
                    <button onClick={() => toggleModuleExpand(mod.name)} className="flex items-center gap-2 flex-1">
                      {expandedModules.includes(mod.name) ? <ChevronDown className="h-5 w-5 text-purple-400" /> : <ChevronRight className="h-5 w-5 text-purple-400" />}
                      <Folder className="h-5 w-5 text-yellow-400" /><span className="flex-1 text-left text-white font-medium">{mod.name}</span>
                    </button>
                    <Badge className="bg-purple-500/30 text-purple-200">{mod.total_videos} videos</Badge>
                  </div>
                  {expandedModules.includes(mod.name) && <div className="pl-8 pb-2 space-y-1">
                    {mod.chapters.map((ch, ci) => {
                      const ck = `${mod.name}|${ch.name}`; const cs = isChapterSelected(mod.name, ch.name)
                      return <div key={ci} className="bg-white/5 rounded-lg overflow-hidden ml-2">
                        <div className="flex items-center gap-3 p-2 hover:bg-white/5">
                          <Checkbox checked={cs === true} onCheckedChange={() => toggleChapter(mod.name, ch.name)} className="border-white/50 data-[state=checked]:bg-blue-500" />
                          <button onClick={() => toggleChapterExpand(ck)} className="flex items-center gap-2 flex-1">
                            {expandedChapters.includes(ck) ? <ChevronDown className="h-4 w-4 text-purple-400" /> : <ChevronRight className="h-4 w-4 text-purple-400" />}
                            <Folder className="h-4 w-4 text-blue-400" /><span className="flex-1 text-left text-purple-100 text-sm">{ch.name}</span>
                          </button>
                          <Badge variant="outline" className="border-purple-400/30 text-purple-300 text-xs">{ch.video_count}</Badge>
                        </div>
                        {expandedChapters.includes(ck) && <div className="pl-8 pb-2 space-y-1">
                          {ch.videos.map((v, vi) => <div key={vi} className="flex items-center gap-2 p-2 ml-2 rounded hover:bg-white/5">
                            <Checkbox checked={selectedVideos.has(v.lesson_id)} onCheckedChange={() => toggleVideo(v.lesson_id)} className="border-white/50 data-[state=checked]:bg-green-500" />
                            <FileVideo className="h-4 w-4 text-pink-400" /><span className="flex-1 text-sm text-purple-100 truncate">{v.title}</span>
                            <a href={v.url} target="_blank" rel="noopener noreferrer" className="text-xs text-pink-400 hover:underline">Open</a>
                          </div>)}
                        </div>}
                      </div>
                    })}
                  </div>}
                </div>
              })}
            </div></ScrollArea>}
          </CardContent>
        </Card>
        <div className="text-center mt-8 text-purple-300 text-sm"><p>Videos organized: Module / Chapter / Video.mp4</p></div>
      </div>
    </div>
  )
}

export default App
