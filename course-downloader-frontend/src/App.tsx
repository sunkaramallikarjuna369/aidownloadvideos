import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Download, LogIn, FileVideo, FileText, Folder, CheckCircle, AlertCircle, Loader2, RefreshCw, Eye, EyeOff } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ModuleItem {
  type: string
  name: string
  url: string
}

interface Module {
  id: string
  name: string
  items: ModuleItem[]
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
  const [modules, setModules] = useState<Module[]>([])
  const [selectedModules, setSelectedModules] = useState<string[]>([])
  
  const [downloadId, setDownloadId] = useState('')
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

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
        setModules(data.modules || [])
        setSuccess(`Successfully logged in! Found ${data.modules?.length || 0} modules.`)
        setSelectedModules(data.modules?.map((m: Module) => m.id) || [])
      } else {
        setError(data.error || data.message || 'Login failed')
      }
    } catch (err) {
      setError('Failed to connect to server. Make sure the backend is running.')
    } finally {
      setIsLoading(false)
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
    setSelectedModules(modules.map(m => m.id))
  }

  const deselectAllModules = () => {
    setSelectedModules([])
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
          module_ids: selectedModules
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

  const totalItems = modules.reduce((sum, m) => sum + (m.items?.length || 0), 0)
  const selectedItemsCount = modules
    .filter(m => selectedModules.includes(m.id))
    .reduce((sum, m) => sum + (m.items?.length || 0), 0)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Course Content Downloader</h1>
          <p className="text-gray-300">Download videos and PDFs from your online courses</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-slate-800/50 border-slate-700">
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
                  placeholder="https://your-course-platform.com/course"
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

              <div className="flex gap-2 pt-2">
                <Button 
                  onClick={handleLogin} 
                  disabled={isLoading}
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Logging in...
                    </>
                  ) : (
                    <>
                      <LogIn className="mr-2 h-4 w-4" />
                      Login & Scan
                    </>
                  )}
                </Button>
                <Button 
                  onClick={handleScanPage} 
                  disabled={isLoading}
                  variant="outline"
                  className="border-slate-600 text-gray-200 hover:bg-slate-700"
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Scan Only
                </Button>
              </div>

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

          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Folder className="h-5 w-5" />
                Course Modules
                {modules.length > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {modules.length} modules
                  </Badge>
                )}
              </CardTitle>
              <CardDescription className="text-gray-400">
                Select modules to download ({selectedItemsCount} of {totalItems} items selected)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {modules.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <Folder className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No modules found yet.</p>
                  <p className="text-sm">Login to your course to see available content.</p>
                </div>
              ) : (
                <>
                  <div className="flex gap-2 mb-4">
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={selectAllModules}
                      className="border-slate-600 text-gray-200 hover:bg-slate-700"
                    >
                      Select All
                    </Button>
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={deselectAllModules}
                      className="border-slate-600 text-gray-200 hover:bg-slate-700"
                    >
                      Deselect All
                    </Button>
                  </div>
                  
                  <ScrollArea className="h-64 rounded-md border border-slate-700 p-4">
                    <div className="space-y-3">
                      {modules.map((module) => (
                        <div 
                          key={module.id} 
                          className="flex items-start space-x-3 p-3 rounded-lg bg-slate-700/50 hover:bg-slate-700 transition-colors"
                        >
                          <Checkbox
                            id={`module-${module.id}`}
                            checked={selectedModules.includes(module.id)}
                            onCheckedChange={() => toggleModuleSelection(module.id)}
                            className="mt-1"
                          />
                          <div className="flex-1 min-w-0">
                            <label 
                              htmlFor={`module-${module.id}`}
                              className="text-sm font-medium text-white cursor-pointer block truncate"
                            >
                              {module.name}
                            </label>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {module.items?.slice(0, 5).map((item, idx) => (
                                <Badge 
                                  key={idx} 
                                  variant="outline" 
                                  className="text-xs border-slate-600 text-gray-300"
                                >
                                  {getItemIcon(item.type)}
                                  <span className="ml-1 truncate max-w-24">{item.name}</span>
                                </Badge>
                              ))}
                              {(module.items?.length || 0) > 5 && (
                                <Badge variant="outline" className="text-xs border-slate-600 text-gray-300">
                                  +{(module.items?.length || 0) - 5} more
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {modules.length > 0 && (
          <Card className="mt-6 bg-slate-800/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Download className="h-5 w-5" />
                Download Content
              </CardTitle>
              <CardDescription className="text-gray-400">
                Download selected modules as videos and PDFs
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button 
                onClick={startDownload} 
                disabled={isDownloading || selectedModules.length === 0}
                className="w-full bg-green-600 hover:bg-green-700"
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
                    Download {selectedModules.length} Module{selectedModules.length !== 1 ? 's' : ''}
                  </>
                )}
              </Button>

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
        )}

        <footer className="mt-8 text-center text-gray-500 text-sm">
          <p>Course Content Downloader - Download your course materials locally</p>
        </footer>
      </div>
    </div>
  )
}

export default App
