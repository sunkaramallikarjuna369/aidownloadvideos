import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Download, LogIn, FileVideo, FileText, Folder, CheckCircle, AlertCircle, Loader2, Eye, EyeOff, BookOpen, GraduationCap, ClipboardList, Award, ChevronDown, ChevronRight, Play, Video, RefreshCw } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Video extraction result interface
interface ExtractedVideo {
  title: string
  url: string
  module: string
  chapter: string
  lesson_id: string
}

// QpiAI Explorer sections - mirrors the site structure
const SECTIONS = [
  { id: 'overview', name: 'Course Overview', icon: BookOpen },
  { id: 'modules', name: 'Modules', icon: Folder },
  { id: 'quizzes', name: 'Quizzes & Assignments', icon: ClipboardList },
  { id: 'certificate', name: 'Certificate', icon: Award },
]

interface ModuleItem {
  type: string
  name: string
  url: string
}

interface Module {
  id: string
  name: string
  section?: string
  status?: string
  items: ModuleItem[]
}

interface SectionData {
  id: string
  name: string
  items: Module[]
}

interface DownloadProgress {
  status: string
  total_items: number
  completed_items: number
  current_item: string
  errors: string[]
  downloaded_files: { module: string; file: string; path: string; type: string }[]
}

function App() {
  const [courseUrl, setCourseUrl] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  
  const [sessionId, setSessionId] = useState('')
  const [sections, setSections] = useState<SectionData[]>([])
  const [activeSection, setActiveSection] = useState('modules')
  const [selectedModules, setSelectedModules] = useState<string[]>([])
  
    const [downloadId, setDownloadId] = useState('')
    const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null)
    const [isDownloading, setIsDownloading] = useState(false)
    const [downloadPath, setDownloadPath] = useState('')
    const [expandedModules, setExpandedModules] = useState<string[]>([])
    
    // New state for API-based video extraction
    const [extractedVideos, setExtractedVideos] = useState<ExtractedVideo[]>([])
    const [isExtracting, setIsExtracting] = useState(false)
    const [extractionProgress, setExtractionProgress] = useState('')
    const [showVideoList, setShowVideoList] = useState(false)

    // Toggle module expansion to show/hide files inside
    const toggleModuleExpansion = (moduleId: string) => {
      setExpandedModules(prev => 
        prev.includes(moduleId) 
          ? prev.filter(id => id !== moduleId)
          : [...prev, moduleId]
      )
    }

    // Expand all modules
    const expandAllModules = () => {
      setExpandedModules(modules.map(m => m.id))
    }

    // Collapse all modules
    const collapseAllModules = () => {
      setExpandedModules([])
    }

  // Get modules for the active section
  const currentSectionData = sections.find(s => s.id === activeSection)
  const modules = currentSectionData?.items || []

  const handleLogin = async () => {
    if (!courseUrl || !username || !password) {
      setError('Please fill in all fields')
      return
    }

    setIsLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_url: courseUrl,
          username: username,
          password: password
        })
      })

      const data = await response.json()

      if (data.success) {
        setSessionId(data.session_id)
        
        // Organize modules into sections (mirroring QpiAI structure)
        const allModules = data.modules || []
        const sectionData: SectionData[] = [
          { id: 'overview', name: 'Course Overview', items: [] },
          { id: 'modules', name: 'Modules', items: allModules },
          { id: 'quizzes', name: 'Quizzes & Assignments', items: data.quizzes || [] },
          { id: 'certificate', name: 'Certificate', items: data.certificate || [] },
        ]
        setSections(sectionData)
        setActiveSection('modules')
        setSuccess(`Successfully logged in! Found ${allModules.length} modules.`)
        setSelectedModules(allModules.map((m: Module) => m.id))
      } else {
        setError(data.error || data.message || 'Login failed')
      }
    } catch (err) {
      setError('Failed to connect to server. Make sure the backend is running.')
    } finally {
      setIsLoading(false)
    }
  }

  // New API-based video extraction - more reliable than DOM scraping
  const handleExtractVideos = async () => {
    if (!courseUrl || !username || !password) {
      setError('Please fill in all fields')
      return
    }

    setIsExtracting(true)
    setError('')
    setSuccess('')
    setExtractionProgress('Logging in and fetching course structure...')

    try {
      const response = await fetch(`${API_URL}/api/extract-videos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_url: courseUrl,
          username: username,
          password: password
        })
      })

      const data = await response.json()

      if (data.success) {
        setSessionId(data.session_id)
        setExtractedVideos(data.videos || [])
        setShowVideoList(true)
        setSuccess(`Found ${data.total_videos} videos out of ${data.total_lessons} lessons!`)
      } else {
        setError(data.detail || data.error || 'Video extraction failed')
      }
    } catch (err) {
      setError('Failed to connect to server. Make sure the backend is running.')
    } finally {
      setIsExtracting(false)
      setExtractionProgress('')
    }
  }

  // Download all extracted videos
  const handleDownloadAllVideos = async () => {
    if (!sessionId || extractedVideos.length === 0) {
      setError('No videos to download')
      return
    }

    setIsDownloading(true)
    setError('')

    try {
      const response = await fetch(`${API_URL}/api/download-videos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          video_urls: extractedVideos,
          download_path: downloadPath
        })
      })

      const data = await response.json()
      if (data.success) {
        setDownloadId(data.download_id)
        setSuccess(`Started downloading ${extractedVideos.length} videos...`)
      } else {
        setError(data.detail || 'Failed to start download')
        setIsDownloading(false)
      }
    } catch (err) {
      setError('Failed to start download')
      setIsDownloading(false)
    }
  }

  const handleScanPage = async () => {
    if (!courseUrl) {
      setError('Please enter a course URL')
      return
    }

    setIsLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_URL}/api/scan-page`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_url: courseUrl,
          username: username || '',
          password: password || ''
        })
      })

      const data = await response.json()

      if (data.success) {
        setSessionId(data.session_id)
        setModules(data.modules || [])
        setSuccess(`Page scanned! Found ${data.modules?.length || 0} modules.`)
        setSelectedModules(data.modules?.map((m: Module) => m.id) || [])
      } else {
        setError(data.error || 'Failed to scan page')
      }
    } catch (err) {
      setError('Failed to connect to server. Make sure the backend is running.')
    } finally {
      setIsLoading(false)
    }
  }

  const toggleModuleSelection = (moduleId: string) => {
    setSelectedModules(prev => 
      prev.includes(moduleId) 
        ? prev.filter(id => id !== moduleId)
        : [...prev, moduleId]
    )
  }

  const selectAllModules = () => {
    const allIds = sections.flatMap(s => s.items.map(m => m.id))
    setSelectedModules(allIds)
  }

  const deselectAllModules = () => {
    setSelectedModules([])
  }

  const selectSectionModules = () => {
    const sectionIds = modules.map(m => m.id)
    setSelectedModules(prev => [...new Set([...prev, ...sectionIds])])
  }

  const getSectionIcon = (sectionId: string) => {
    const section = SECTIONS.find(s => s.id === sectionId)
    if (section) {
      const Icon = section.icon
      return <Icon className="h-5 w-5" />
    }
    return <Folder className="h-5 w-5" />
  }

  const startDownload = async () => {
    if (!sessionId || selectedModules.length === 0) {
      setError('Please select at least one module to download')
      return
    }

    setIsDownloading(true)
    setError('')

    try {
      const response = await fetch(`${API_URL}/api/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          module_ids: selectedModules,
          download_path: downloadPath
        })
      })

      const data = await response.json()
      setDownloadId(data.download_id)
    } catch (err) {
      setError('Failed to start download')
      setIsDownloading(false)
    }
  }

  useEffect(() => {
    let interval: NodeJS.Timeout

    if (downloadId && isDownloading) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/api/download/progress/${downloadId}`)
          const data = await response.json()
          setDownloadProgress(data)

          if (data.status === 'completed' || data.status === 'error') {
            setIsDownloading(false)
            clearInterval(interval)
          }
        } catch (err) {
          console.error('Failed to fetch progress')
        }
      }, 1000)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [downloadId, isDownloading])

  const downloadZip = async () => {
    if (!downloadId) return
    
    window.open(`${API_URL}/api/download/zip/${downloadId}`, '_blank')
  }

  const getItemIcon = (type: string) => {
    switch (type) {
      case 'video':
        return <FileVideo className="h-4 w-4 text-blue-500" />
      case 'pdf':
        return <FileText className="h-4 w-4 text-red-500" />
      default:
        return <Folder className="h-4 w-4 text-gray-500" />
    }
  }

  const totalItems = sections.flatMap(s => s.items).reduce((sum, m) => sum + (m.items?.length || 0), 0)
  const selectedItemsCount = sections
    .flatMap(s => s.items)
    .filter(m => selectedModules.includes(m.id))
    .reduce((sum, m) => sum + (m.items?.length || 0), 0)

  const isLoggedIn = sessionId && sections.length > 0

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Course Content Downloader</h1>
          <p className="text-gray-300">Download videos and PDFs - Mirrors QpiAI Explorer structure</p>
        </div>

        {!isLoggedIn ? (
          // Login Form
          <Card className="max-w-md mx-auto bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <LogIn className="h-5 w-5" />
                Login to Course
              </CardTitle>
              <CardDescription className="text-gray-400">
                Enter your course URL and credentials to access the content
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="courseUrl" className="text-gray-200">Course URL</Label>
                <Input
                  id="courseUrl"
                  placeholder="https://explorer-dev.qpiai.tech/learn/..."
                  value={courseUrl}
                  onChange={(e) => setCourseUrl(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-400"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="username" className="text-gray-200">Username / Email</Label>
                <Input
                  id="username"
                  placeholder="your@email.com"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-400"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password" className="text-gray-200">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-400 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="downloadPath" className="text-gray-200">Download Location (optional)</Label>
                <Input
                  id="downloadPath"
                  placeholder="D:\Downloads\QpiAI_Course"
                  value={downloadPath}
                  onChange={(e) => setDownloadPath(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-400"
                />
                <p className="text-xs text-gray-500">Leave empty to use default location</p>
              </div>

              <Button 
                onClick={handleExtractVideos} 
                disabled={isExtracting || isLoading}
                className="w-full bg-green-600 hover:bg-green-700"
              >
                {isExtracting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Extracting Videos... (This takes a while)
                  </>
                ) : (
                  <>
                    <Video className="mr-2 h-4 w-4" />
                    Extract All Video URLs
                  </>
                )}
              </Button>

              {extractionProgress && (
                <p className="text-sm text-gray-400 text-center">{extractionProgress}</p>
              )}

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-slate-600" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-slate-800 px-2 text-gray-500">Or use legacy mode</span>
                </div>
              </div>

              <Button 
                onClick={handleLogin} 
                disabled={isLoading || isExtracting}
                variant="outline"
                className="w-full border-slate-600 text-gray-200 hover:bg-slate-700"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Logging in...
                  </>
                ) : (
                  <>
                    <LogIn className="mr-2 h-4 w-4" />
                    Login & Scan (Legacy)
                  </>
                )}
              </Button>

              {error && (
                <Alert variant="destructive" className="bg-red-900/50 border-red-800">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {success && (
                <Alert className="bg-green-900/50 border-green-800">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <AlertTitle className="text-green-400">Success</AlertTitle>
                  <AlertDescription className="text-green-300">{success}</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        ) : showVideoList && extractedVideos.length > 0 ? (
          // Video List View - Shows all extracted videos
          <div className="max-w-4xl mx-auto space-y-6">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Video className="h-5 w-5" />
                  Extracted Videos ({extractedVideos.length})
                </CardTitle>
                <CardDescription className="text-gray-400">
                  All video URLs have been extracted. Click "Download All" to start downloading.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Button 
                    onClick={handleDownloadAllVideos}
                    disabled={isDownloading}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {isDownloading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        Download All Videos
                      </>
                    )}
                  </Button>
                  <Button 
                    onClick={() => {
                      setShowVideoList(false)
                      setExtractedVideos([])
                      setSessionId('')
                    }}
                    variant="outline"
                    className="border-slate-600 text-gray-200 hover:bg-slate-700"
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Start Over
                  </Button>
                </div>

                {downloadProgress && (
                  <div className="space-y-2 p-4 bg-slate-700/50 rounded-lg">
                    <div className="flex justify-between text-sm text-gray-300">
                      <span>Progress: {downloadProgress.completed_items} / {downloadProgress.total_items}</span>
                      <span>{downloadProgress.status}</span>
                    </div>
                    <Progress 
                      value={downloadProgress.total_items > 0 
                        ? (downloadProgress.completed_items / downloadProgress.total_items) * 100 
                        : 0
                      } 
                      className="h-2"
                    />
                    {downloadProgress.current_item && (
                      <p className="text-sm text-gray-400 truncate">
                        Current: {downloadProgress.current_item}
                      </p>
                    )}
                    {downloadProgress.status === 'completed' && (
                      <Alert className="bg-green-900/50 border-green-800 mt-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <AlertTitle className="text-green-400">Download Complete!</AlertTitle>
                        <AlertDescription className="text-green-300">
                          All videos have been downloaded to your specified location.
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                )}

                <ScrollArea className="h-96 rounded border border-slate-600">
                  <div className="p-4 space-y-2">
                    {/* Group videos by module */}
                    {Array.from(new Set(extractedVideos.map(v => v.module))).map(moduleName => (
                      <div key={moduleName} className="mb-4">
                        <h3 className="text-sm font-medium text-purple-400 mb-2 flex items-center gap-2">
                          <Folder className="h-4 w-4" />
                          {moduleName}
                        </h3>
                        <div className="pl-4 space-y-1">
                          {extractedVideos
                            .filter(v => v.module === moduleName)
                            .map((video, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-sm text-gray-300 py-1 hover:bg-slate-700/50 rounded px-2">
                                <FileVideo className="h-4 w-4 text-blue-400 flex-shrink-0" />
                                <span className="truncate flex-1">{video.title}</span>
                                <a 
                                  href={video.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-xs text-blue-400 hover:underline flex-shrink-0"
                                >
                                  Open
                                </a>
                              </div>
                            ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        ) : (
          // Main Content - Mirrors QpiAI Structure with Sidebar
          <div className="flex gap-6">
            {/* Left Sidebar - QpiAI Navigation */}
            <div className="w-64 flex-shrink-0">
              <Card className="bg-slate-800/50 border-slate-700 sticky top-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-white text-lg flex items-center gap-2">
                    <GraduationCap className="h-5 w-5" />
                    Course Content
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <nav className="space-y-1">
                    {SECTIONS.map((section) => {
                      const sectionData = sections.find(s => s.id === section.id)
                      const itemCount = sectionData?.items.length || 0
                      const Icon = section.icon
                      
                      return (
                        <button
                          key={section.id}
                          onClick={() => setActiveSection(section.id)}
                          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                            activeSection === section.id
                              ? 'bg-purple-600 text-white'
                              : 'text-gray-300 hover:bg-slate-700'
                          }`}
                        >
                          <Icon className="h-5 w-5" />
                          <span className="flex-1">{section.name}</span>
                          {itemCount > 0 && (
                            <Badge variant="secondary" className="text-xs">
                              {itemCount}
                            </Badge>
                          )}
                        </button>
                      )
                    })}
                  </nav>
                  
                  <div className="mt-4 pt-4 border-t border-slate-700">
                    <p className="text-xs text-gray-500 mb-2">
                      {selectedModules.length} items selected
                    </p>
                    <Button 
                      onClick={selectAllModules}
                      size="sm"
                      variant="outline"
                      className="w-full border-slate-600 text-gray-200 hover:bg-slate-700 mb-2"
                    >
                      Select All Sections
                    </Button>
                    <Button 
                      onClick={deselectAllModules}
                      size="sm"
                      variant="outline"
                      className="w-full border-slate-600 text-gray-200 hover:bg-slate-700"
                    >
                      Deselect All
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 space-y-6">
              {/* Section Content */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    {getSectionIcon(activeSection)}
                    {SECTIONS.find(s => s.id === activeSection)?.name}
                    {modules.length > 0 && (
                      <Badge variant="secondary" className="ml-2">
                        {modules.length} items
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription className="text-gray-400">
                    {activeSection === 'modules' && 'Course modules with videos and learning materials'}
                    {activeSection === 'overview' && 'Course overview and introduction'}
                    {activeSection === 'quizzes' && 'Quizzes and assignments for this course'}
                    {activeSection === 'certificate' && 'Your course completion certificate'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {modules.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">
                      <Folder className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>No content found in this section.</p>
                      {activeSection !== 'modules' && (
                        <p className="text-sm mt-2">This section may not have downloadable content.</p>
                      )}
                    </div>
                  ) : (
                    <>
                                            <div className="flex gap-2 mb-4">
                                              <Button 
                                                size="sm" 
                                                variant="outline" 
                                                onClick={selectSectionModules}
                                                className="border-slate-600 text-gray-200 hover:bg-slate-700"
                                              >
                                                Select All in Section
                                              </Button>
                                              <Button 
                                                size="sm" 
                                                variant="outline" 
                                                onClick={expandAllModules}
                                                className="border-slate-600 text-gray-200 hover:bg-slate-700"
                                              >
                                                Expand All
                                              </Button>
                                              <Button 
                                                size="sm" 
                                                variant="outline" 
                                                onClick={collapseAllModules}
                                                className="border-slate-600 text-gray-200 hover:bg-slate-700"
                                              >
                                                Collapse All
                                              </Button>
                                            </div>
                      
                      {/* Table Header - Mirrors QpiAI */}
                      <div className="grid grid-cols-12 gap-4 px-4 py-2 bg-slate-700/50 rounded-t-lg text-sm font-medium text-gray-300">
                        <div className="col-span-1">S.No</div>
                        <div className="col-span-8">Title</div>
                        <div className="col-span-3">Status</div>
                      </div>
                      
                                            <ScrollArea className="h-96 rounded-b-md border border-slate-700 border-t-0">
                                              <div className="divide-y divide-slate-700">
                                                {modules.map((module, index) => (
                                                  <div key={module.id}>
                                                    {/* Module Row */}
                                                    <div 
                                                      className="grid grid-cols-12 gap-4 px-4 py-3 hover:bg-slate-700/50 transition-colors items-center cursor-pointer"
                                                      onClick={() => module.items?.length > 0 && toggleModuleExpansion(module.id)}
                                                    >
                                                      <div className="col-span-1 text-gray-400 text-sm flex items-center gap-1">
                                                        {module.items?.length > 0 && (
                                                          expandedModules.includes(module.id) 
                                                            ? <ChevronDown className="h-4 w-4" />
                                                            : <ChevronRight className="h-4 w-4" />
                                                        )}
                                                        {index + 1}
                                                      </div>
                                                      <div className="col-span-8 flex items-center gap-3">
                                                        <Checkbox
                                                          id={`module-${module.id}`}
                                                          checked={selectedModules.includes(module.id)}
                                                          onCheckedChange={(e) => {
                                                            e.stopPropagation?.()
                                                            toggleModuleSelection(module.id)
                                                          }}
                                                          onClick={(e) => e.stopPropagation()}
                                                        />
                                                        <Folder className="h-4 w-4 text-yellow-500" />
                                                        <label 
                                                          htmlFor={`module-${module.id}`}
                                                          className="text-sm text-white cursor-pointer flex-1 font-medium"
                                                        >
                                                          {module.name}
                                                        </label>
                                                        {module.items?.length > 0 && (
                                                          <Badge variant="outline" className="text-xs border-purple-600 text-purple-300">
                                                            {module.items.length} files
                                                          </Badge>
                                                        )}
                                                      </div>
                                                      <div className="col-span-3">
                                                        <Badge 
                                                          variant="outline" 
                                                          className={`text-xs ${
                                                            module.status === 'Completed' 
                                                              ? 'border-green-600 text-green-400' 
                                                              : 'border-slate-600 text-gray-400'
                                                          }`}
                                                        >
                                                          {module.status || 'Not Started'}
                                                        </Badge>
                                                      </div>
                                                    </div>
                              
                                                    {/* Expanded Files List */}
                                                    {expandedModules.includes(module.id) && module.items?.length > 0 && (
                                                      <div className="bg-slate-900/50 border-l-2 border-purple-600 ml-8">
                                                        {module.items.map((item, itemIndex) => (
                                                          <div 
                                                            key={`${module.id}-item-${itemIndex}`}
                                                            className="grid grid-cols-12 gap-4 px-4 py-2 hover:bg-slate-700/30 transition-colors items-center"
                                                          >
                                                            <div className="col-span-1 text-gray-500 text-xs pl-4">
                                                              {itemIndex + 1}
                                                            </div>
                                                            <div className="col-span-8 flex items-center gap-3">
                                                              {item.type === 'video' ? (
                                                                <Play className="h-4 w-4 text-blue-400" />
                                                              ) : item.type === 'pdf' ? (
                                                                <FileText className="h-4 w-4 text-red-400" />
                                                              ) : (
                                                                <FileVideo className="h-4 w-4 text-green-400" />
                                                              )}
                                                              <span className="text-sm text-gray-300">
                                                                {item.name}
                                                              </span>
                                                            </div>
                                                            <div className="col-span-3">
                                                              <Badge 
                                                                variant="outline" 
                                                                className="text-xs border-blue-600 text-blue-300"
                                                              >
                                                                {item.type}
                                                              </Badge>
                                                            </div>
                                                          </div>
                                                        ))}
                                                      </div>
                                                    )}
                                                  </div>
                                                ))}
                                              </div>
                                            </ScrollArea>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Download Section */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Download className="h-5 w-5" />
                    Download Content
                  </CardTitle>
                  <CardDescription className="text-gray-400">
                    Download selected content ({selectedItemsCount} of {totalItems} items)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="downloadPath" className="text-gray-300">
                      Download Location (optional)
                    </Label>
                    <Input
                      id="downloadPath"
                      type="text"
                      placeholder="e.g., D:\Downloads\Courses or leave empty for default"
                      value={downloadPath}
                      onChange={(e) => setDownloadPath(e.target.value)}
                      className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-500"
                    />
                    <p className="text-xs text-gray-500">
                      Files will be organized in folders matching the course structure.
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <Button 
                      onClick={() => {
                        selectAllModules()
                        setTimeout(startDownload, 100)
                      }} 
                      disabled={isDownloading || sections.flatMap(s => s.items).length === 0}
                      className="flex-1 bg-purple-600 hover:bg-purple-700"
                      size="lg"
                    >
                      {isDownloading ? (
                        <>
                          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                          Downloading...
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 h-5 w-5" />
                          Download Everything
                        </>
                      )}
                    </Button>
                    <Button 
                      onClick={startDownload} 
                      disabled={isDownloading || selectedModules.length === 0}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                      size="lg"
                    >
                      {isDownloading ? (
                        <>
                          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                          Downloading...
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 h-5 w-5" />
                          Download Selected ({selectedModules.length})
                        </>
                      )}
                    </Button>
                  </div>

                  {downloadProgress && (
                    <div className="space-y-4 p-4 rounded-lg bg-slate-700/50">
                      <div className="flex justify-between text-sm text-gray-300">
                        <span>Progress: {downloadProgress.completed_items} / {downloadProgress.total_items}</span>
                        <Badge 
                          variant={downloadProgress.status === 'completed' ? 'default' : 'secondary'}
                          className={downloadProgress.status === 'completed' ? 'bg-green-600' : ''}
                        >
                          {downloadProgress.status}
                        </Badge>
                      </div>
                      
                      <Progress 
                        value={downloadProgress.total_items > 0 
                          ? (downloadProgress.completed_items / downloadProgress.total_items) * 100 
                          : 0
                        } 
                        className="h-2"
                      />
                      
                      {downloadProgress.current_item && (
                        <p className="text-sm text-gray-400 truncate">
                          Current: {downloadProgress.current_item}
                        </p>
                      )}

                      {downloadProgress.status === 'completed' && (
                        <div className="space-y-3">
                          <Alert className="bg-green-900/50 border-green-800">
                            <CheckCircle className="h-4 w-4 text-green-500" />
                            <AlertTitle className="text-green-400">Download Complete!</AlertTitle>
                            <AlertDescription className="text-green-300">
                              Successfully downloaded {downloadProgress.downloaded_files?.length || 0} files.
                            </AlertDescription>
                          </Alert>
                          
                          <Button 
                            onClick={downloadZip}
                            className="w-full bg-blue-600 hover:bg-blue-700"
                          >
                            <Download className="mr-2 h-4 w-4" />
                            Download as ZIP
                          </Button>
                        </div>
                      )}

                      {downloadProgress.errors?.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-sm font-medium text-red-400">Errors:</p>
                          <ScrollArea className="h-24 rounded border border-red-800 p-2">
                            {downloadProgress.errors.map((err, idx) => (
                              <p key={idx} className="text-xs text-red-300">{err}</p>
                            ))}
                          </ScrollArea>
                        </div>
                      )}

                      {downloadProgress.downloaded_files?.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-sm font-medium text-gray-300">Downloaded Files:</p>
                          <ScrollArea className="h-32 rounded border border-slate-600 p-2">
                            {downloadProgress.downloaded_files.map((file, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-xs text-gray-400 py-1">
                                {getItemIcon(file.type)}
                                <span className="truncate">{file.module} / {file.file}</span>
                              </div>
                            ))}
                          </ScrollArea>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        <footer className="mt-8 text-center text-gray-500 text-sm">
          <p>Course Content Downloader - Mirrors QpiAI Explorer structure</p>
        </footer>
      </div>
    </div>
  )
}

export default App
